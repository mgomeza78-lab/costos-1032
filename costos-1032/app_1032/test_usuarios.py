# -*- coding: utf-8 -*-
"""Pruebas de administración de usuarios:

  · un Analista puede quedar asignado a VARIAS empresas (usuario_empresa) al crearlo;
  · el administrador puede reasignar ese conjunto (y vaciarlo = todas);
  · el administrador puede restablecer la contraseña de un usuario (cambio obligatorio);
  · autorización: un usuario que no es administrador no puede ejecutar estas acciones;
  · solo los analistas admiten asignación a varias empresas.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db, security

PW = config.SEED_PASSWORD
NUEVA = "Reasignar2026*"
TEST_EMAIL = "multi.analista@test.co"
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def csrf(cli, path="/usuarios"):
    m = re.search(r'name="csrf-token" content="([^"]+)"', cli.get(path).text)
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


def q(sql, **p):
    with db.engine_owner.begin() as conn:
        return conn.execute(text(sql), p).all()


def empresas_de(uid):
    return sorted(r[0] for r in q("SELECT empresa_id FROM usuario_empresa WHERE usuario_id=:u", u=uid))


def uid_de(email):
    r = q("SELECT id FROM usuario WHERE email=:e", e=email)
    return r[0][0] if r else None


# limpieza previa (reejecutable)
with db.engine_owner.begin() as c:
    c.execute(text("DELETE FROM usuario WHERE email=:e"), {"e": TEST_EMAIL})

admin = cli("mgomeza78@gmail.com")

# ---------- 1) la página carga con la gestión y el control de analista ----------
print("== Página de usuarios ==")
html = admin.get("/usuarios").text
check(admin.get("/usuarios").status_code == 200, "GET /usuarios responde 200 al admin")
check("Gestionar usuarios" in html, "la sección 'Gestionar usuarios' está presente")
check('name="empresas_analista"' in html, "el formulario ofrece asignación de empresas al analista")

# ---------- 2) crear un analista con DOS empresas ----------
print("== Crear analista multiempresa ==")
r = admin.post("/usuarios", data={
    "nombre": "Analista Multi", "email": TEST_EMAIL, "rol": "analista",
    "empresa_id": "", "empresas_analista": ["1", "2"], "password": NUEVA,
    "csrf": csrf(admin)}, follow_redirects=False)
check("Credencial+emitida" in r.headers.get("location", ""), "el alta responde 'Credencial emitida'")
uid = uid_de(TEST_EMAIL)
check(uid is not None, "el usuario quedó creado")
check(empresas_de(uid) == [1, 2], f"usuario_empresa = {{1,2}} (obtenido {empresas_de(uid)})")
sc = db.resolve_scope(uid)
check(sc["allow_all"] is False and sorted(sc["empresa_ids"]) == [1, 2],
      f"app_scope: NO todas, empresas {{1,2}} (obtenido {sc})")

# ---------- 3) reasignar a UNA sola empresa ----------
print("== Reasignar empresas del analista ==")
r = admin.post(f"/usuarios/{uid}/empresas", data={
    "empresas_analista": ["3"], "csrf": csrf(admin)}, follow_redirects=False)
check("Empresas+asignadas" in r.headers.get("location", ""), "la reasignación confirma")
check(empresas_de(uid) == [3], f"usuario_empresa = {{3}} (obtenido {empresas_de(uid)})")
check(sorted(db.resolve_scope(uid)["empresa_ids"]) == [3], "app_scope refleja solo la empresa 3")

# ---------- 4) vaciar la asignación => ve todas ----------
print("== Vaciar asignación (todas) ==")
r = admin.post(f"/usuarios/{uid}/empresas", data={"csrf": csrf(admin)}, follow_redirects=False)
check(empresas_de(uid) == [], "usuario_empresa quedó vacío")
check(db.resolve_scope(uid)["allow_all"] is True, "app_scope: analista sin asignación ve TODAS")

# ---------- 5) restablecer contraseña (admin) ----------
print("== Restablecer contraseña ==")
r = admin.post(f"/usuarios/{uid}/password", data={
    "password": "Nueva1234*", "csrf": csrf(admin)}, follow_redirects=False)
check("restablecida" in r.headers.get("location", ""), "el reset confirma")
fila = q("SELECT password_hash, debe_cambiar_pass FROM usuario WHERE id=:u", u=uid)[0]
check(security.verify_password("Nueva1234*", fila[0]), "la nueva contraseña es válida")
check(not security.verify_password(NUEVA, fila[0]), "la contraseña anterior ya no sirve")
check(fila[1] is True, "queda marcada para cambio obligatorio")

# ---------- 6) contraseña débil es rechazada ----------
print("== Validación de política ==")
r = admin.post(f"/usuarios/{uid}/password", data={
    "password": "corta", "csrf": csrf(admin)}, follow_redirects=False)
loc = r.headers.get("location", "")
check("err=" in loc and "restablecida" not in loc, "una contraseña débil es rechazada")

# ---------- 7) solo analistas admiten varias empresas ----------
print("== Guardas de rol ==")
aud = uid_de("auditor@sspd.gov.co")
r = admin.post(f"/usuarios/{aud}/empresas", data={
    "empresas_analista": ["1", "2"], "csrf": csrf(admin)}, follow_redirects=False)
check("Solo+los+analistas" in r.headers.get("location", ""),
      "asignar varias empresas a un NO-analista es rechazado")
check(empresas_de(aud) == [], "al auditor no se le escribió ninguna asignación")

# ---------- 8) autorización: un no-admin no puede ----------
print("== Autorización ==")
op = cli("operador.neiva@lasceibas.gov.co")
r = op.post(f"/usuarios/{uid}/password", data={
    "password": "Hackeo2026*", "csrf": csrf(op, "/empresa/1")}, follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), "un operador NO puede restablecer contraseñas")
fila = q("SELECT password_hash FROM usuario WHERE id=:u", u=uid)[0]
check(not security.verify_password("Hackeo2026*", fila[0]), "la contraseña del operador no se aplicó")
r = op.post(f"/usuarios/{uid}/empresas", data={
    "empresas_analista": ["1"], "csrf": csrf(op, "/empresa/1")}, follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), "un operador NO puede asignar empresas")

# limpieza
with db.engine_owner.begin() as c:
    c.execute(text("DELETE FROM usuario WHERE email=:e"), {"e": TEST_EMAIL})

print()
if _fail:
    print(f"RESULTADO: {len(_fail)} comprobación(es) fallida(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
