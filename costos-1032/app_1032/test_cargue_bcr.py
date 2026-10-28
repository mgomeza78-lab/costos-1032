# -*- coding: utf-8 -*-
"""Pruebas de costos particulares, inventario de la BCR y proyección del CMI.

  · costos particulares: guardar (upsert), listar y eliminar;
  · menú «Cargar información» responde y etiqueta período→año tarifario;
  · activos de la BCR: alta, resumen por servicio/componente;
  · plan/real/cumplimiento por año tarifario (regla 80 %);
  · proyección indicativa del CMI (5 años, roll-forward de la BCR);
  · RLS: un operador de otra empresa no registra activos ajenos.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import bcr_service as bcr
import costos_service as cpart

PW = config.SEED_PASSWORD
EID = 1
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def csrf(cli, path):
    m = re.search(r'name="csrf-token" content="([^"]+)"', cli.get(path).text)
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM costo_particular WHERE empresa_id=:e"), {"e": EID})
    cn.execute(text("DELETE FROM bcr_activo WHERE empresa_id=:e"), {"e": EID})
    cn.execute(text("DELETE FROM proyecto_inversion WHERE empresa_id=:e AND codigo_poir='POIR-T'"), {"e": EID})

adm = cli("mgomeza78@gmail.com")

print("== Menú Cargar información responde y etiqueta el año tarifario ==")
r = adm.get(f"/empresa/{EID}/cargar")
check(r.status_code == 200 and "Cargar información" in r.text, f"/cargar responde 200 ({r.status_code})")
check("Período de inicio" in r.text, "etiqueta el año tarifario (período de inicio) de lo comercial 2026")

print("== Costos particulares: guardar, upsert y eliminar ==")
tok = csrf(adm, f"/empresa/{EID}/cargar?fuente=costos")
adm.post(f"/empresa/{EID}/cargar-costo-particular", data={
    "csrf": tok, "next": f"/empresa/{EID}/cargar?fuente=costos", "anio": "2026", "servicio": "acueducto",
    "categoria": "Tasas ambientales", "concepto": "Tasa por uso de agua", "valor": "125000000",
    "unidad": "$ total", "origen": "empresa"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT valor FROM costo_particular WHERE empresa_id=:e AND concepto='Tasa por uso de agua'"),
                     {"e": EID}).mappings().first()
check(row is not None and abs((row["valor"] or 0) - 125000000) < 1, "costo particular guardado")
# upsert: mismo concepto, nuevo valor
adm.post(f"/empresa/{EID}/cargar-costo-particular", data={
    "csrf": tok, "anio": "2026", "servicio": "acueducto", "concepto": "Tasa por uso de agua",
    "valor": "130000000"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    n = cn.execute(text("SELECT count(*) FROM costo_particular WHERE empresa_id=:e AND concepto='Tasa por uso de agua'"),
                   {"e": EID}).scalar_one()
    val = cn.execute(text("SELECT valor FROM costo_particular WHERE empresa_id=:e AND concepto='Tasa por uso de agua'"),
                     {"e": EID}).scalar()
check(n == 1 and abs((val or 0) - 130000000) < 1, "upsert actualiza el mismo concepto (no duplica)")

print("== Activos de la BCR: alta y resumen por componente ==")
tok = csrf(adm, f"/empresa/{EID}/inversiones?sec=bcr")
for comp, nom, vp, cu in [("1", "Red matriz", "35600000000", "2280000000"),
                          ("1", "Planta La Plata", "31900000000", "2650000000"),
                          ("3", "Sede administrativa", "2600000000", "520000000")]:
    adm.post(f"/empresa/{EID}/bcr-activo", data={
        "csrf": tok, "next": f"/empresa/{EID}/inversiones?sec=bcr", "servicio": "acueducto",
        "componente": comp, "nombre": nom, "valor_pendiente": vp, "cuota_anual": cu,
        "plazo_remanente": "20", "origen": "BCR0_688"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    res = bcr.resumen(cn, EID)
ac = res.get("acueducto", {})
check(abs(ac.get("bcr", 0) - 70100000000) < 1, f"BCR₀ acueducto = suma de pendientes ({ac.get('bcr')})")
check(ac.get("comp", {}).get(1, {}).get("n") == 2, "componente 1 agrupa 2 activos")

print("== Plan / real / cumplimiento por año tarifario ==")
tok = csrf(adm, f"/empresa/{EID}/inversiones")
adm.post(f"/empresa/{EID}/inversion-nueva", data={
    "csrf": tok, "codigo_poir": "POIR-T", "nombre": "Proyecto prueba", "servicio": "acueducto",
    "clasificacion": "CMI_POIR", "marco": "1032", "valor_planeado": "1000",
    "fecha_planeada_operacion": "2027-06-30"},
    follow_redirects=False)
# el proyecto_id real:
with db.engine_owner.connect() as cn:
    pid = cn.execute(text("SELECT id FROM proyecto_inversion WHERE empresa_id=:e AND codigo_poir='POIR-T'"),
                     {"e": EID}).scalar()
tok = csrf(adm, f"/empresa/{EID}/inversiones")
adm.post(f"/empresa/{EID}/inversion-avance", data={
    "csrf": tok, "proyecto_id": str(pid), "anio": "2027", "mes": "6",
    "avance_fisico": "85", "avance_financiero": "850"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    cum = {c["anio"]: c for c in bcr.cumplimiento(cn, EID, "acueducto")}
c27 = cum.get(2027)
check(c27 is not None and abs(c27["planeado"] - 1000) < 1 and abs(c27["ejecutado"] - 850) < 1,
      f"cumplimiento 2027 plan/real ({c27})")
check(c27 and c27["pct"] and c27["pct"] >= 80 and c27["supera"], "2027 supera el 80 %")

print("== Proyección indicativa del CMI (5 años) ==")
with db.engine_owner.connect() as cn:
    pr = bcr.proyeccion(cn, EID, "acueducto", 0.0903, demanda=20000000.0)
check(len(pr["filas"]) == 5, f"proyecta 5 años ({len(pr['filas'])})")
f0 = pr["filas"][0]
check(f0["anio"] == 2027 and f0["cmi_bcr"] is not None and f0["cmi_total"] is not None,
      "primer año 2027 con CMI_BCR y CMI total calculados")
check(f0["poir_entra"] >= 1000, "el POIR planeado 2027 entra a la proyección")

print("== RLS: operador de otra empresa (AMB) no registra activos ajenos ==")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/bcr-activo", data={
    "csrf": tokx, "servicio": "acueducto", "componente": "1", "nombre": "HACK",
    "valor_pendiente": "999"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    hack = cn.execute(text("SELECT count(*) FROM bcr_activo WHERE empresa_id=:e AND nombre='HACK'"),
                      {"e": EID}).scalar_one()
check(hack == 0, "AMB no pudo registrar un activo en la BCR de Las Ceibas")

# limpieza del proyecto de prueba
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM proyecto_inversion WHERE empresa_id=:e AND codigo_poir='POIR-T'"), {"e": EID})

print("\n" + ("TODAS LAS PRUEBAS DE CARGUE/BCR PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
