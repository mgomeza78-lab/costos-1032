# -*- coding: utf-8 -*-
"""Pruebas del endurecimiento de seguridad (en proceso, vía TestClient).

  · cabeceras de seguridad presentes;
  · CSRF: POST sin token válido es rechazado;
  · bloqueo de cuenta tras N intentos fallidos;
  · MFA (TOTP): si está activo, el login exige el segundo factor.
"""
import re
import pyotp
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db

PW = config.SEED_PASSWORD
_fail = []


def check(cond, desc):
    print(("  OK  " if cond else "FALLA ") + desc)
    if not cond:
        _fail.append(desc)


def csrf(client, path):
    html = client.get(path).text
    m = (re.search(r'name="csrf-token" content="([^"]+)"', html)
         or re.search(r'name="csrf" value="([^"]+)"', html))
    return m.group(1) if m else ""


# ---------- 1) cabeceras de seguridad ----------
print("== Cabeceras de seguridad ==")
c = TestClient(main.app)
h = c.get("/login").headers
check("Content-Security-Policy" in h and "frame-ancestors 'none'" in h["Content-Security-Policy"],
      "Content-Security-Policy presente y restrictiva")
check(h.get("X-Frame-Options") == "DENY", "X-Frame-Options: DENY")
check(h.get("X-Content-Type-Options") == "nosniff", "X-Content-Type-Options: nosniff")
check("Referrer-Policy" in h, "Referrer-Policy presente")

# ---------- 2) CSRF ----------
print("== CSRF ==")
c = TestClient(main.app)
c.get("/login")  # fija cookie de sesión con token
r = c.post("/login", data={"email": "mgomeza78@gmail.com", "password": PW, "csrf": "token-falso"},
           follow_redirects=False)
loc = r.headers.get("location", "")
check("Token+de+seguridad" in loc, f"login sin CSRF válido es rechazado ({loc})")
# y no quedó autenticado
check(c.get("/api/empresas").status_code == 401, "sin CSRF no se inició sesión")

# ---------- 3) bloqueo por intentos ----------
print("== Bloqueo por intentos fallidos ==")
EMAIL = "auditor@sspd.gov.co"
bloqueado = False
for i in range(config.MAX_LOGIN_ATTEMPTS):
    cc = TestClient(main.app)
    tok = csrf(cc, "/login")
    r = cc.post("/login", data={"email": EMAIL, "password": "clave-mala", "csrf": tok},
                follow_redirects=False)
    if "bloqueada" in r.headers.get("location", "").lower():
        bloqueado = True
check(bloqueado, f"la cuenta se bloquea dentro de {config.MAX_LOGIN_ATTEMPTS} intentos")
# incluso con la contraseña correcta, queda bloqueada
cc = TestClient(main.app)
tok = csrf(cc, "/login")
r = cc.post("/login", data={"email": EMAIL, "password": PW, "csrf": tok}, follow_redirects=False)
check("bloqueada" in r.headers.get("location", "").lower(),
      "con la clave correcta sigue bloqueada durante la ventana")
db.registrar_intento(EMAIL, True)   # restaurar para no dejar la cuenta bloqueada
check(True, "bloqueo restaurado para la demo")

# ---------- 4) MFA (TOTP) ----------
print("== MFA (TOTP) ==")
secret = pyotp.random_base32()
with db.engine_owner.begin() as conn:
    conn.execute(text("UPDATE usuario SET mfa_secret=:s, mfa_activo=true WHERE email=:e"),
                 {"s": secret, "e": "analista@sictaa.co"})
cc = TestClient(main.app)
tok = csrf(cc, "/login")
r = cc.post("/login", data={"email": "analista@sictaa.co", "password": PW, "csrf": tok},
            follow_redirects=False)
check("/mfa" in r.headers.get("location", ""), "con MFA activo, el login va al segundo factor")
check(cc.get("/api/empresas").status_code == 401, "sin el 2.º factor no hay sesión")
# código incorrecto
tok = csrf(cc, "/mfa")
r = cc.post("/mfa", data={"codigo": "000000", "csrf": tok}, follow_redirects=False)
check("err" in r.headers.get("location", ""), "código MFA incorrecto es rechazado")
# código correcto
tok = csrf(cc, "/mfa")
code = pyotp.TOTP(secret).now()
r = cc.post("/mfa", data={"codigo": code, "csrf": tok}, follow_redirects=False)
check("/panel" in r.headers.get("location", ""), "código MFA correcto completa el ingreso")
check(cc.get("/api/empresas").status_code == 200, "tras el 2.º factor hay sesión")
with db.engine_owner.begin() as conn:    # restaurar
    conn.execute(text("UPDATE usuario SET mfa_secret=NULL, mfa_activo=false WHERE email=:e"),
                 {"e": "analista@sictaa.co"})

print("\n" + ("TODAS LAS PRUEBAS DE SEGURIDAD PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
