# -*- coding: utf-8 -*-
"""Pruebas del factor de ajuste del ISUF (Fap) del CCP (tabla del parágrafo 3, Res. CRA 1032)."""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import ccp_service as ccp

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


def fap(ir, ivh, met, cm):
    return ccp.fap_resuelto({"aplica": True, "ipuf_real": ir, "ivh": ivh, "metodologia": met,
                             "cumplio_meta": cm})[0]


print("== Tabla del Fap (casos de la Res. 1032) ==")
check(fap(17.35, "alta", "688", False) == 1.60, "IPUF>15 · alta · 688 · meta No → 1,60 (caso Las Ceibas)")
check(fap(17.35, "alta", "688", True) == 3.20, "IPUF>15 · alta · 688 · meta Sí → 3,20")
check(fap(7, "baja", "825", None) == 0.78, "6<IPUF≤8 · baja · 825 → 0,78")
check(fap(9, "muy_alta", "688", False) == 0.33, "8<IPUF≤11,5 · muy alta · 688 · No → 0,33")
check(fap(13, "media", "688", True) == 2.00, "11,5<IPUF≤15 · media · 688 · Sí → 2,00")
check(fap(5, "baja", "688", False) == 0.0, "IPUF≤6 → Fap 0 (ya en el estándar)")
check(ccp.fap_resuelto({"aplica": False, "ipuf_real": 17, "ivh": "alta", "metodologia": "688", "cumplio_meta": False})[0] == 0.0,
      "ajuste no aplicado (optativo) → Fap 0")
check(fap(10, None, "688", False) is None, "sin IVH → Fap pendiente (None)")

print("== Cumplimiento de meta (diferencia ≤ 20 %) ==")
check(ccp.cumplimiento_meta(12.0, 14.0) is True, "planeado 12, real 14 → diferencia 16,7 % ≤ 20 % → cumplió")
check(ccp.cumplimiento_meta(12.0, 15.0) is False, "planeado 12, real 15 → diferencia 25 % > 20 % → no cumplió")

print("== Ruta: guardar y resolver el Fap ==")
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM ccp_fap WHERE empresa_id=:e"), {"e": EID})
adm = cli("mgomeza78@gmail.com")
NXA = f"/empresa/{EID}/cargar?fuente=agua"    # el Fap vive en el Paso 3 (Producción y Suministro de Agua)
tok = csrf(adm, NXA)
# Fap ÚNICO por empresa: el IPUFreal, la metodología y el cumplimiento los calcula el sistema desde lo
# cargado; el usuario solo aporta el IVH y las metas del IPUF de la 688 (años 9 y 10).
r = adm.post(f"/empresa/{EID}/ccp-fap", data={
    "csrf": tok, "next": NXA, "aplica": "on", "ivh": "alta",
    "ipuf_meta_a9": "8", "ipuf_meta_a10": "8"}, follow_redirects=False)
check("msg=" in r.headers.get("location", ""), "guardado del Fap OK (ruta nueva: IVH + metas 688)")
with db.engine_owner.connect() as cn:
    row = ccp.get(cn, EID)
check(row is not None, "fila única del Fap creada (una por empresa)")
check(row and row["metodologia"] in ("688", "825"),
      f"metodología derivada del punto de partida ({row['metodologia'] if row else None})")
check(row and row["ivh"] == "alta", "IVH guardado")
# La resolución exacta de la tabla del Fap (rango × IVH × metodología × cumplimiento) se verifica
# arriba en fap_resuelto(...); aquí el IPUFreal depende de lo cargado, por eso no se fija su valor.

print("== La pestaña Agua/Fap responde ==")
check(adm.get(NXA).status_code == 200 and "ajuste del ISUF" in adm.get(NXA).text, "la pestaña Agua/Fap renderiza")

print("== RLS: AMB no edita el Fap de Las Ceibas ==")
with db.engine_owner.connect() as cn:
    fap_prev = (ccp.get(cn, EID) or {}).get("fap")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/ccp-fap", data={"csrf": tokx, "aplica": "on", "ivh": "baja",
         "ipuf_meta_a9": "6", "ipuf_meta_a10": "6"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = ccp.get(cn, EID)
check(row and row["ivh"] == "alta" and (row["fap"] == fap_prev),
      "AMB no alteró el Fap de Las Ceibas")

print("\n" + ("TODAS LAS PRUEBAS DE CCP/FAP PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
