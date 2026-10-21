# -*- coding: utf-8 -*-
"""Pruebas de costos particulares alineados a los modelos y su resta del COC.

  · captura con cantidad, precio unitario, valor reconocido, cuenta contable y valor contable;
  · ajuste al COC = Σ valor contable por servicio/año (no doble conteo, art. 2.1.2.1.3.4.4/.5);
  · la vista muestra la resta al COC;
  · RLS: un operador de otra empresa no carga costos particulares ajenos.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
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

adm = cli("mgomeza78@gmail.com")
NX = f"/empresa/{EID}/cargar?fuente=costos"
tok = csrf(adm, NX)

print("== Captura de costos particulares con cuenta y valor contable ==")
adm.post(f"/empresa/{EID}/cargar-costo-particular", data={
    "csrf": tok, "next": NX, "anio": "2026", "servicio": "acueducto", "categoria": "Energía (CE)",
    "concepto": "Energía bombeo PTAP", "cantidad": "1000000", "precio_unitario": "600",
    "valor": "600000000", "unidad": "$ total", "cuenta_contable": "7503",
    "valor_contable": "580000000", "origen": "empresa"}, follow_redirects=False)
adm.post(f"/empresa/{EID}/cargar-costo-particular", data={
    "csrf": tok, "next": NX, "anio": "2026", "servicio": "acueducto", "categoria": "Insumos químicos (CIQ)",
    "concepto": "Cloro y coagulante", "valor": "150000000", "cuenta_contable": "750502",
    "valor_contable": "120000000", "origen": "empresa"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT cantidad, precio_unitario, valor, cuenta_contable, valor_contable "
                          "FROM costo_particular WHERE empresa_id=:e AND concepto='Energía bombeo PTAP'"),
                     {"e": EID}).mappings().first()
check(row is not None and row["cuenta_contable"] == "7503"
      and abs((row["valor_contable"] or 0) - 580000000) < 1, "cuenta y valor contable guardados")
check(row and abs((row["cantidad"] or 0) - 1000000) < 1 and abs((row["precio_unitario"] or 0) - 600) < 1,
      "cantidad y precio unitario guardados (alineado a los modelos)")

print("== Ajuste al COC (resta por no doble conteo) ==")
with db.engine_owner.connect() as cn:
    aj = cpart.ajuste_coc(cn, EID)
ac = next((a for a in aj if a["servicio"] == "acueducto" and a["anio"] == 2026), None)
check(ac is not None and abs(ac["resta_coc"] - 700000000) < 1,
      f"resta al COC = Σ valor contable (580M + 120M = 700M) ({ac['resta_coc'] if ac else None})")
check(ac and ac["n"] == 2, "cuenta 2 costos particulares con valor contable")

print("== La vista muestra la resta al COC ==")
r = adm.get(NX)
check(r.status_code == 200 and "Resta al COC" in r.text, "la pestaña de costos muestra la resta al COC")

print("== RLS: operador de otra empresa (AMB) no carga costos ajenos ==")
amb = cli("operador@amb.com.co")
tokx = csrf(amb, "/panel")
amb.post(f"/empresa/{EID}/cargar-costo-particular", data={
    "csrf": tokx, "anio": "2026", "servicio": "acueducto", "concepto": "HACK",
    "valor_contable": "999"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    n = cn.execute(text("SELECT count(*) FROM costo_particular WHERE empresa_id=:e AND concepto='HACK'"),
                   {"e": EID}).scalar_one()
check(n == 0, "AMB no cargó un costo particular en Las Ceibas")

print("\n" + ("TODAS LAS PRUEBAS DE COSTOS/COC PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
