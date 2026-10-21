# -*- coding: utf-8 -*-
"""Prueba de aislamiento multiempresa end-to-end (en proceso, vía TestClient).

Verifica, atravesando autenticación + sesión + CSRF + rutas + RLS:
  · el Administrador ve las 3 empresas;
  · un usuario Empresa ve SOLO la suya;
  · un usuario Empresa NO puede leer los costos de otra (404);
  · un usuario Empresa NO puede recalcular (rol sin permiso);
  · el Administrador sí recalcula.
"""
import re
from starlette.testclient import TestClient
import config, main

PW = config.SEED_PASSWORD
LAS_CEIBAS, ESSMAR, AMB = 1, 2, 3
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


def cli(email):
    c = TestClient(main.app)
    tok = csrf(c, "/login")
    r = c.post("/login", data={"email": email, "password": PW, "csrf": tok}, follow_redirects=False)
    assert r.status_code == 303, f"login {email} -> {r.status_code}"
    return c


print("== Administrador (consultor): ve todas ==")
admin = cli("mgomeza78@gmail.com")
j = admin.get("/api/empresas").json()
check(len(j["empresas"]) == 3, f"admin ve 3 empresas (vio {len(j['empresas'])})")
check(j["rol"] == "admin", "admin tiene rol admin")

print("== Usuario Empresa (ESSMAR): ve solo la suya ==")
essmar = cli("operador@essmar.gov.co")
j = essmar.get("/api/empresas").json()
codigos = [e["codigo"] for e in j["empresas"]]
check(len(j["empresas"]) == 1 and codigos == ["ESSMAR"], f"ESSMAR ve solo ESSMAR (vio {codigos})")

print("== Aislamiento: ESSMAR intenta ver costos de Las Ceibas ==")
r = essmar.get(f"/api/empresa/{LAS_CEIBAS}/costos")
check(r.status_code == 404, f"acceso cruzado bloqueado (HTTP {r.status_code})")
j = essmar.get(f"/api/empresa/{ESSMAR}/costos").json()
check("costos" in j and len(j["costos"]) > 0, f"ESSMAR sí ve sus costos ({len(j.get('costos',[]))} filas)")

print("== Permisos: usuario Empresa NO puede recalcular ==")
tok = csrf(essmar, f"/empresa/{ESSMAR}")
r = essmar.post(f"/empresa/{ESSMAR}/recalcular", data={"csrf": tok}, follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), f"recalcular como Empresa -> rechazado ({r.headers.get('location')})")

print("== Admin SÍ puede recalcular cualquier empresa ==")
tok = csrf(admin, f"/empresa/{AMB}")
r = admin.post(f"/empresa/{AMB}/recalcular", data={"csrf": tok}, follow_redirects=False)
check("aplicado" in r.headers.get("location", ""), f"admin recalcula amb ({r.headers.get('location')})")

print("== Auditor (solo lectura de Las Ceibas) ==")
aud = cli("auditor@sspd.gov.co")
j = aud.get("/api/empresas").json()
check(len(j["empresas"]) == 1 and j["empresas"][0]["codigo"] == "LAS_CEIBAS", "auditor ve solo Las Ceibas")
tok = csrf(aud, f"/empresa/{LAS_CEIBAS}")
r = aud.post(f"/empresa/{LAS_CEIBAS}/recalcular", data={"csrf": tok}, follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), "auditor no puede recalcular")

print("\n" + ("TODAS LAS PRUEBAS PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
