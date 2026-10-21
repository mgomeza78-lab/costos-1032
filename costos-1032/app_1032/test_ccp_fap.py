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
NX = f"/empresa/{EID}/cargar?fuente=ccp"
tok = csrf(adm, NX)
r = adm.post(f"/empresa/{EID}/ccp-fap", data={
    "csrf": tok, "next": NX, "servicio": "acueducto", "aplica": "on", "ipuf_real": "17.35",
    "ivh": "alta", "metodologia": "688", "cumplio": "no"}, follow_redirects=False)
check("msg=" in r.headers.get("location", ""), "guardado del Fap OK")
with db.engine_owner.connect() as cn:
    row = ccp.get(cn, EID, "acueducto")
check(row is not None and abs((row["fap"] or 0) - 1.60) < 1e-9, f"Fap guardado = 1,60 ({row['fap'] if row else None})")

# cumplimiento automático desde IPUF planeado/real
adm.post(f"/empresa/{EID}/ccp-fap", data={
    "csrf": tok, "next": NX, "servicio": "acueducto", "aplica": "on", "ipuf_real": "13",
    "ivh": "media", "metodologia": "688", "cumplio": "", "ipuf_planeado": "12"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = ccp.get(cn, EID, "acueducto")
# real 13 vs planeado 12 → diferencia 8,3 % ≤ 20 % → cumplió → 11,5<IPUF≤15·media·688·Sí = 2,00
check(row and row["cumplio_meta"] is True and abs((row["fap"] or 0) - 2.00) < 1e-9,
      f"cumplimiento automático → Fap 2,00 ({row['fap'] if row else None})")

print("== La pestaña CCP responde ==")
check(adm.get(NX).status_code == 200 and "ajuste del ISUF" in adm.get(NX).text, "la pestaña CCP/Fap renderiza")

print("== RLS: AMB no edita el Fap de Las Ceibas ==")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/ccp-fap", data={"csrf": tokx, "servicio": "acueducto", "aplica": "on",
         "ipuf_real": "7", "ivh": "baja", "metodologia": "825"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = ccp.get(cn, EID, "acueducto")
check(row and abs((row["fap"] or 0) - 2.00) < 1e-9, "AMB no alteró el Fap de Las Ceibas")

print("\n" + ("TODAS LAS PRUEBAS DE CCP/FAP PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
