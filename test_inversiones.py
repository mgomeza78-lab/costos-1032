# -*- coding: utf-8 -*-
"""Pruebas del módulo de Inversiones/POIR (en proceso, vía TestClient).

  · crear proyecto con los campos de la 1032;
  · registrar avance → transición de estado (en ejecución / en operación);
  · % de ejecución y resumen por servicio (umbral 80 %);
  · clasificación inválida rechazada;
  · aislamiento: un usuario Empresa no crea ni ve proyectos de otra empresa.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import inversiones_service as inv

PW = config.SEED_PASSWORD
LAS_CEIBAS, ESSMAR = 1, 2
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def csrf(cli, path):
    h = cli.get(path).text
    m = (re.search(r'name="csrf-token" content="([^"]+)"', h)
         or re.search(r'name="csrf" value="([^"]+)"', h))
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


admin = cli("mgomeza78@gmail.com")

print("== Crear proyecto (admin, Las Ceibas) ==")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/inversiones")
r = admin.post(f"/empresa/{LAS_CEIBAS}/inversion-nueva", data={
    "codigo_poir": "TEST-AC-900", "nombre": "Proyecto de prueba", "servicio": "acueducto",
    "componente_sistema": "tratamiento", "meta_asociada": "calidad", "clasificacion": "CMI_POIR",
    "origen": "POIR_nuevo", "valor_planeado": "1000000000", "fecha_planeada_operacion": "2026-12-31",
    "csrf": tok}, follow_redirects=False)
check("guardado" in r.headers.get("location", ""), f"proyecto creado ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    pid = cn.execute(text("SELECT id, estado FROM proyecto_inversion WHERE empresa_id=:e AND "
                          "codigo_poir='TEST-AC-900'"), {"e": LAS_CEIBAS}).mappings().first()
check(pid is not None and pid["estado"] == "planeado", "estado inicial = planeado")

print("== Registrar avance: pasa a 'en ejecución' ==")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/inversiones")
r = admin.post(f"/empresa/{LAS_CEIBAS}/inversion-avance", data={
    "proyecto_id": pid["id"], "anio": 2026, "mes": 7, "avance_fisico": "40",
    "avance_financiero": "400000000", "csrf": tok}, follow_redirects=False)
check("Avance+registrado" in r.headers.get("location", ""), "avance registrado")
with db.engine_owner.connect() as cn:
    est = cn.execute(text("SELECT estado FROM proyecto_inversion WHERE id=:p"), {"p": pid["id"]}).scalar()
check(est == "en_ejecucion", f"estado → en ejecución ({est})")

print("== Avance 100 % + fecha real: pasa a 'en operación' ==")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/inversiones")
admin.post(f"/empresa/{LAS_CEIBAS}/inversion-avance", data={
    "proyecto_id": pid["id"], "anio": 2026, "mes": 9, "avance_fisico": "100",
    "avance_financiero": "1000000000", "fecha_real_operacion": "2026-09-15", "csrf": tok},
    follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT estado, fecha_real_operacion FROM proyecto_inversion WHERE id=:p"),
                     {"p": pid["id"]}).mappings().first()
check(row["estado"] == "en_operacion" and str(row["fecha_real_operacion"]) == "2026-09-15",
      f"estado → en operación con fecha real ({row['estado']}, {row['fecha_real_operacion']})")

print("== Resumen por servicio y % de ejecución ==")
with db.engine_owner.connect() as cn:
    res = inv.resumen(cn, LAS_CEIBAS)
check(res["n"] >= 1 and res["tot_plan"] > 0, f"resumen con proyectos ({res['n']}, plan {res['tot_plan']:,.0f})")
check("acueducto" in res["por_servicio"], "resumen por servicio presente")
# el proyecto de prueba quedó 100% ejecutado
with db.engine_owner.connect() as cn:
    pct = cn.execute(text("SELECT avance_financiero FROM avance_inversion WHERE proyecto_id=:p "
                          "ORDER BY anio DESC, mes DESC LIMIT 1"), {"p": pid["id"]}).scalar()
check(pct == 1000000000, "avance financiero acumulado = planeado (100%)")

print("== Clasificación inválida rechazada ==")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/inversiones")
r = admin.post(f"/empresa/{LAS_CEIBAS}/inversion-nueva", data={
    "codigo_poir": "TEST-BAD", "nombre": "x", "servicio": "acueducto",
    "clasificacion": "INVENTADA", "csrf": tok}, follow_redirects=False)
check("clasificaci" in r.headers.get("location", "").lower(), "clasificación inválida rechazada")

print("== Aislamiento: ESSMAR no crea ni ve proyectos de Las Ceibas ==")
essmar = cli("operador@essmar.gov.co")
r = essmar.get(f"/empresa/{LAS_CEIBAS}/inversiones", follow_redirects=False)
check("no+disponible" in r.headers.get("location", "").lower() or "panel" in r.headers.get("location", ""),
      f"ESSMAR no ve inversiones de Las Ceibas ({r.headers.get('location')})")
tok = csrf(essmar, f"/empresa/{ESSMAR}/inversiones")
r = essmar.post(f"/empresa/{LAS_CEIBAS}/inversion-nueva", data={
    "codigo_poir": "INTRUSO-1", "nombre": "x", "servicio": "acueducto", "csrf": tok},
    follow_redirects=False)
with db.engine_owner.connect() as cn:
    intruso = cn.execute(text("SELECT count(*) FROM proyecto_inversion WHERE empresa_id=:e AND "
                              "codigo_poir='INTRUSO-1'"), {"e": LAS_CEIBAS}).scalar_one()
check(intruso == 0, "no quedó proyecto intruso en Las Ceibas")

# limpieza del proyecto de prueba
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM proyecto_inversion WHERE empresa_id=:e AND codigo_poir IN "
                    "('TEST-AC-900','TEST-BAD')"), {"e": LAS_CEIBAS})

print("\n" + ("TODAS LAS PRUEBAS DE INVERSIONES PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
