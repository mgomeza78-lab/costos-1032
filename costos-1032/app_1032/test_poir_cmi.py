# -*- coding: utf-8 -*-
"""Pruebas de ingresos por proyecto: CMI por activo y modificaciones del POIR.

  · registrar nº de modificaciones y fechas;
  · cargar un Excel de CMI por activo por cada modificación (upsert de activos + CMI);
  · CMI aplicable según la modificación vigente en cada año;
  · VP(CMI×Q) por activo → VPR₀ → VA₀ → BCR₀ (con VIA del POIR desde la ejecución);
  · plantilla Excel descargable;
  · RLS: un operador de otra empresa no carga el CMI ajeno.
"""
import io
import re
import openpyxl
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import bcr_service as bcr

PW = config.SEED_PASSWORD
EID = 1
N = f"/empresa/{EID}/inversiones?sec=bcr"
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


def xlsx(rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["codigo", "nombre", "componente", "origen", "via688", "prr", "ejecucion_real", "anio_poir", "cmi"])
    for r in rows:
        ws.append(r)
    b = io.BytesIO(); wb.save(b); return b.getvalue()


with db.engine_owner.begin() as cn:
    for tb in ("activo_cmi", "poir_modificacion", "bcr_activo", "bcr_param", "bcr_serie"):
        cn.execute(text(f"DELETE FROM {tb} WHERE empresa_id=:e"), {"e": EID})

adm = cli("mgomeza78@gmail.com")
tok = csrf(adm, N)

print("== Parámetros, series y modificaciones ==")
adm.post(f"/empresa/{EID}/bcr-param", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "r688": "0.1485", "ipc_dic_2014": "114.0",
    "ipc_dic_2025": "180.0", "fecha_inicio_688": "2016-07-01", "ccp_2025": "20000000"}, follow_redirects=False)
for i, q, c in [(1, "19000000", "700"), (2, "19200000", "700"), (3, "19400000", "700"), (4, "19600000", "800")]:
    adm.post(f"/empresa/{EID}/bcr-serie", data={"csrf": tok, "next": N, "servicio": "acueducto",
             "anio_tarifario": str(i), "q_m3": q, "cmi_cobrado": c}, follow_redirects=False)
r = adm.post(f"/empresa/{EID}/bcr-poir-mods", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "fechas": "2019-07-01"}, follow_redirects=False)
check("modificaciones" in r.headers.get("location", ""), "modificaciones del POIR registradas")
with db.engine_owner.connect() as cn:
    mods = cn.execute(text("SELECT numero,fecha FROM poir_modificacion WHERE empresa_id=:e AND servicio='acueducto' ORDER BY numero"), {"e": EID}).all()
check(len(mods) == 2 and str(mods[0][1]) == "2016-07-01", f"mod 0 = inicio 688 ({mods[0][1]})")

print("== Carga de un Excel de CMI por modificación ==")
f0 = xlsx([["AC-001", "Red matriz", 1, "VI287", 100000000000, 20, "", "", 700],
           ["AC-002", "Ampliación POIR", 1, "POIR688", "", 40, 50000000000, 2, 100]])
r0 = adm.post(f"/empresa/{EID}/bcr-poir-cmi",
              data={"csrf": tok, "next": N, "servicio": "acueducto", "modificacion": "0"},
              files={"archivo": ("mod0.xlsx", f0, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
              follow_redirects=False)
check("2+CMI+cargados" in r0.headers.get("location", ""), f"mod 0 cargada ({r0.headers.get('location')})")
f1 = xlsx([["AC-001", "Red matriz", 1, "VI287", 100000000000, 20, "", "", 800],
           ["AC-002", "Ampliación POIR", 1, "POIR688", "", 40, 50000000000, 2, 130]])
adm.post(f"/empresa/{EID}/bcr-poir-cmi",
         data={"csrf": tok, "next": N, "servicio": "acueducto", "modificacion": "1"},
         files={"archivo": ("mod1.xlsx", f1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
         follow_redirects=False)
with db.engine_owner.connect() as cn:
    nact = cn.execute(text("SELECT count(*) FROM bcr_activo WHERE empresa_id=:e AND servicio='acueducto'"), {"e": EID}).scalar_one()
    ncmi = cn.execute(text("SELECT count(*) FROM activo_cmi WHERE empresa_id=:e AND servicio='acueducto'"), {"e": EID}).scalar_one()
check(nact == 2, f"2 activos creados desde el Excel ({nact})")
check(ncmi == 4, f"4 CMI (2 activos × 2 modificaciones) ({ncmi})")

print("== CMI aplicable por modificación y cálculo de la BCR₀ ==")
import poir_cmi_service as poir
with db.engine_owner.connect() as cn:
    cc = poir.cmi_por_codigo(cn, EID, "acueducto")
    mods_l = poir.mods_list(cn, EID, "acueducto")
    # año 1 (2016) → mod 0 = 700; año 4 (inicia 2019-07-01) → mod 1 = 800
    cmi_a1 = poir.cmi_aplicable(mods_l, cc["AC-001"], poir._year_start if False else __import__("datetime").date(2016, 7, 1))
    cmi_a4 = poir.cmi_aplicable(mods_l, cc["AC-001"], __import__("datetime").date(2019, 7, 1))
    b = bcr.bcr0_calculo(cn, EID, 0.0903)["acueducto"]
    via_poir = bcr.via_de_ejecucion({"via688": None, "ejecucion_real": 5000000000, "anio_poir": 5}, 0.1485)
check(cc["AC-001"] == {0: 700.0, 1: 800.0}, f"CMI de AC-001 por modificación ({cc['AC-001']})")
check(cmi_a1 == 700.0 and cmi_a4 == 800.0, f"CMI vigente: año1=700, año4=800 ({cmi_a1},{cmi_a4})")
check(via_poir and abs(via_poir - 5000000000/((1.1485)**5)) < 1.0, "VIA del POIR = ejecución/(1+r688)^año")
check(b["bcr"] and b["bcr"] > 0 and b["cmi_bcr"] is not None, f"BCR₀ y CMI_BCR calculados ({b['bcr']:.0f}, {b['cmi_bcr']:.2f})")

print("== Plantilla Excel descargable ==")
rp = adm.get(f"/empresa/{EID}/bcr-poir-plantilla")
check(rp.status_code == 200 and rp.content[:2] == b"PK", "la plantilla descarga un .xlsx válido")

print("== RLS: operador de otra empresa (AMB) no carga CMI ajeno ==")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/bcr-poir-cmi", data={"csrf": tokx, "servicio": "acueducto", "modificacion": "0"},
         files={"archivo": ("x.xlsx", f0, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
         follow_redirects=False)
with db.engine_owner.connect() as cn:
    nact2 = cn.execute(text("SELECT count(*) FROM bcr_activo WHERE empresa_id=:e AND servicio='acueducto'"), {"e": EID}).scalar_one()
check(nact2 == 2, "AMB no alteró los activos de Las Ceibas")

print("\n" + ("TODAS LAS PRUEBAS DE CMI POR PROYECTO PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
