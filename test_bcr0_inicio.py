# -*- coding: utf-8 -*-
"""Pruebas de la reconstrucción de la BCR₀ de inicio (marco 688) en Inversiones · CMI/POIR.

  · parámetros 688 (r688, IPC dic-2014/2025, inicio 688, CCP) y series (agua facturada, CMI cobrado);
  · VA₀ calculado desde VPR₀ con (1+r688)^t·fa0;
  · compensación de VA₀<0 contra activos con pendiente>0 (art. 2.1.2.1.5.2.1.1);
  · BCR₀, cak, CI y CMI_BCR;
  · RLS: un operador de otra empresa no edita los parámetros 688 ajenos.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import bcr_service as bcr

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
    cn.execute(text("DELETE FROM bcr_activo WHERE empresa_id=:e"), {"e": EID})
    cn.execute(text("DELETE FROM bcr_param WHERE empresa_id=:e"), {"e": EID})
    cn.execute(text("DELETE FROM bcr_serie WHERE empresa_id=:e"), {"e": EID})

adm = cli("mgomeza78@gmail.com")
N = f"/empresa/{EID}/inversiones?sec=bcr"
tok = csrf(adm, N)

print("== Parámetros 688 y series ==")
adm.post(f"/empresa/{EID}/bcr-param", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "r688": "0.1485",
    "ipc_dic_2014": "114.0", "ipc_dic_2025": "180.0", "fecha_inicio_688": "2016-07-01",
    "ccp_2025": "20000000"}, follow_redirects=False)
adm.post(f"/empresa/{EID}/bcr-serie", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "anio_tarifario": "1",
    "q_m3": "19000000", "cmi_cobrado": "700"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    p = bcr.param_get(cn, EID, "acueducto")
    ser = bcr.serie_list(cn, EID, "acueducto")
check(p is not None and abs(float(p["r688"]) - 0.1485) < 1e-9, "parámetros 688 guardados")
check(len(ser) == 1 and abs((ser[0]["q_m3"] or 0) - 19000000) < 1, "serie de agua facturada / CMI guardada")

print("== Activos: VA₀ calculado desde VPR₀ y compensación de negativos ==")
adm.post(f"/empresa/{EID}/bcr-activo", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "componente": "1", "origen": "VI287",
    "nombre": "Red matriz", "vpr0": "10000000000", "plazo_remanente": "20"}, follow_redirects=False)
adm.post(f"/empresa/{EID}/bcr-activo", data={
    "csrf": tok, "next": N, "servicio": "acueducto", "componente": "1", "origen": "POIR688",
    "nombre": "POIR no operó", "vpr0": "-2000000000", "plazo_remanente": "15"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    pos = cn.execute(text("SELECT va0 FROM bcr_activo WHERE empresa_id=:e AND nombre='Red matriz'"),
                     {"e": EID}).scalar()
    b = bcr.bcr0_calculo(cn, EID, 0.0903)["acueducto"]
check(pos is not None and pos > 6.0e10 and pos < 6.5e10, f"VA₀ del activo positivo calculado desde VPR₀ ({pos:.0f})")
check(abs(b["t"] - 9.9167) < 0.01, f"t = 9,9167 años ({b['t']:.4f})")
check(abs(b["fa0"] - (180.0/114.0)) < 1e-6, f"fa0 = IPC25/IPC14 ({b['fa0']:.4f})")
check(abs(b["descuento"] - 12465127588) < 5e6, f"descuento = |VA₀ negativo| ({b['descuento']:.0f})")
check(abs(b["bcr"] - 49860510351) < 5e6, f"BCR₀ compensada ({b['bcr']:.0f})")
check(b["cmi_bcr"] is not None and abs(b["cmi_bcr"] - 349.77) < 0.5, f"CMI_BCR = CI/CCP ({b['cmi_bcr']:.2f})")
check(abs(b["ci"] - (b["cak"] + b["bcr"] * 0.0903)) < 1.0, "CI = Σcak + BCR₀·r")

print("== VP de los ingresos (CMI×Q) y derivación del VPR₀ desde VIA688 ==")
adm.post(f"/empresa/{EID}/bcr-param", data={
    "csrf": tok, "next": N, "servicio": "alcantarillado", "r688": "0.10",
    "ipc_dic_2014": "100.0", "ipc_dic_2025": "150.0", "fecha_inicio_688": "2016-07-01",
    "ccp_2025": "12000000"}, follow_redirects=False)
adm.post(f"/empresa/{EID}/bcr-serie", data={
    "csrf": tok, "next": N, "servicio": "alcantarillado", "anio_tarifario": "1",
    "q_m3": "10000000", "cmi_cobrado": "500"}, follow_redirects=False)
adm.post(f"/empresa/{EID}/bcr-activo", data={   # solo VIA688, sin VPR₀ → se deriva
    "csrf": tok, "next": N, "servicio": "alcantarillado", "componente": "1", "origen": "VIdif287",
    "nombre": "Colector (solo VIA)", "via688": "20000000000", "plazo_remanente": "18"},
    follow_redirects=False)
with db.engine_owner.connect() as cn:
    ing = bcr.ingresos_vp(cn, EID, "alcantarillado")
    bal = bcr.bcr0_calculo(cn, EID, 0.0903)["alcantarillado"]
check(ing["total"] is not None and abs(ing["total"] - 4545454545) < 5e6,
      f"VP(ingresos) = Σ CMI·Q/(1+r688)^i ({ing['total']:.0f})")
check(abs(bal["vp_ingresos"] - ing["total"]) < 1.0, "el VP de ingresos entra al cálculo de la BCR₀")
check(bal["bcr"] > 5.5e10 and bal["bcr"] < 6.3e10,
      f"VPR₀ derivado de VIA688 − VP(ingresos) → BCR₀ ({bal['bcr']:.0f})")

print("== RLS: un operador de otra empresa (AMB) no edita los parámetros 688 ==")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/bcr-param", data={
    "csrf": tokx, "servicio": "acueducto", "r688": "0.99"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    r = cn.execute(text("SELECT r688 FROM bcr_param WHERE empresa_id=:e AND servicio='acueducto'"),
                   {"e": EID}).scalar()
check(abs(float(r) - 0.1485) < 1e-9, f"AMB no alteró los parámetros 688 de Las Ceibas ({r})")

print("\n" + ("TODAS LAS PRUEBAS DE BCR₀ DE INICIO PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
