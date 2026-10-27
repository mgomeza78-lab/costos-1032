# -*- coding: utf-8 -*-
"""Pruebas del balance de prueba por SUBCOMPONENTE y el reparto por servicio:

  · clasificar_buckets + aplicar_pct: clase 5 reparte por %, clase 7 por el servicio de la cuenta;
  · cargar un balance (año base) guarda numerador_subcomp sin tocar el motor (año < 2026);
  · balance_view.resumen muestra subcomponentes por año y por servicio;
  · cambiar el % de reparto re-reparte la clase 5 al instante (sin recargar el balance).

Usa el año ficticio 2011 en Las Ceibas (empresa 1) y limpia al final.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db, clasificador as clf, balance_view as bv

PW = config.SEED_PASSWORD
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def near(a, b, t=1.0):
    return a is not None and abs(a - b) <= t


# ---------------- 1) Unidad: cubetas + reparto ----------------
print("== clasificar_buckets + aplicar_pct (clase 5 por %, clase 7 por cuenta) ==")
cat = {
    "51010101": ("CAC-1", "CMA", "", ""),             # clase 5 -> reparte por %
    "750201":   ("COC-2", "CMO", "", "acueducto"),    # clase 7 -> acueducto
    "7503040":  ("COC-2", "CMO", "", "alcantarillado"),  # clase 7 -> alcantarillado
}
filas = [
    {"codigo_norm": "51010101", "nombre": "SUELDOS", "saldo_final": 1_000_000.0},
    {"codigo_norm": "750201",   "nombre": "OPER AC", "saldo_final": 600_000.0},
    {"codigo_norm": "75030401", "nombre": "OPER AL", "saldo_final": 400_000.0},  # usa prefijo 7503040
]
buckets, sin = clf.clasificar_buckets(filas, cat)
check(near(buckets[("CMA", "CAC-1")]["repartir"], 1_000_000), "CAC-1 (clase 5) va a 'repartir'")
check(near(buckets[("CMO", "COC-2")]["ac_dir"], 600_000) and near(buckets[("CMO", "COC-2")]["al_dir"], 400_000),
      "COC-2 (clase 7): 600k acueducto + 400k alcantarillado directos")
agg = clf.aplicar_pct(buckets, 0.6)
check(near(agg[("CMA", "CAC-1", "acueducto")], 600_000) and near(agg[("CMA", "CAC-1", "alcantarillado")], 400_000),
      "CAC-1 repartido 60/40 = 600k/400k")
check(near(agg[("CMO", "COC-2", "acueducto")], 600_000), "COC-2 acueducto = 600k (no usa %)")

# ---------------- 2) Carga del balance (año base) + vista ----------------
print("\n== carga de balance año base (2011) → numerador_subcomp + vista ==")
balance_csv = ("CODIGO,NOMBRE,SALDO INICIAL,DEBITO,CREDITO,SALDO FINAL\n"
               "51010101,SUELDOS DE PERSONAL,0,0,0,1000000\n"
               "750201,COSTOS GENERALES OPER,0,0,0,600000\n"
               "75030401,COSTOS OPER ALCANT,0,0,0,400000\n"
               "75111708,ALUMBRADO PUBLICO,0,0,0,200000\n")  # ICTA (clase 5) -> reparte por %


def limpiar():
    with db.engine_owner.begin() as c:
        c.execute(text("DELETE FROM numerador_subcomp WHERE empresa_id=1 AND anio=2011"))
        c.execute(text("DELETE FROM balance_reparto WHERE empresa_id=1"))


limpiar()
c = TestClient(main.app)
m = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/login").text)
c.post("/login", data={"email": "mgomeza78@gmail.com", "password": PW, "csrf": m.group(1)}, follow_redirects=False)


def tok(path):
    h = c.get(path).text
    mm = re.search(r'name="csrf" value="([^"]+)"', h) or re.search(r'name="csrf-token" content="([^"]+)"', h)
    return mm.group(1)


r = c.post("/empresa/1/cargar-balance",
           data={"anio": 2011, "mes_ini": 1, "mes_fin": 12, "cod_dane": "", "csrf": tok("/empresa/1/cargar?fuente=balance"), "next": ""},
           files={"archivo": ("bal2011.csv", balance_csv, "text/csv")}, follow_redirects=False)
check(r.status_code in (302, 303) and "/balance" in r.headers.get("location", ""),
      f"carga redirige a la pantalla de balance ({r.headers.get('location','')[:50]})")

with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    cma = bv.resumen(conn, 1, "CMA", None)        # conjunto, pct default 0.52
    fila_cac1 = next((f for f in cma["filas"] if f["sub"] == "CAC-1"), None)
    check(2011 in cma["anios"], "la vista lista el año 2011 cargado")
    check(fila_cac1 and near(fila_cac1["cols"].get(2011), 1_000_000),
          f"CMA · CAC-1 conjunto 2011 = 1.000.000 (obtenido {fila_cac1['cols'].get(2011) if fila_cac1 else None})")
    cma_ac = bv.resumen(conn, 1, "CMA", "acueducto")
    f_ac = next((f for f in cma_ac["filas"] if f["sub"] == "CAC-1"), None)
    check(f_ac and near(f_ac["cols"].get(2011), 520_000),
          f"CMA · CAC-1 acueducto 2011 = 520.000 (52% de 1.000.000) (obtenido {f_ac['cols'].get(2011) if f_ac else None})")
    cmo = bv.resumen(conn, 1, "CMO", "acueducto")
    tot_cmo_ac = cmo["total"].get(2011)
    check(near(tot_cmo_ac, 600_000), f"CMO acueducto 2011 = 600.000 (cuenta 7502, por cuenta) (obtenido {tot_cmo_ac})")

# ---------------- 3) Cambiar el % re-reparte la clase 5 ----------------
print("\n== cambiar el % de reparto re-reparte la clase 5 ==")
c.post("/empresa/1/balance-reparto",
       data={"pct_ac": "70", "comp": "CMA", "serv": "", "csrf": tok("/empresa/1/balance?comp=CMA")},
       follow_redirects=False)
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    cma_ac = bv.resumen(conn, 1, "CMA", "acueducto")
    f_ac = next((f for f in cma_ac["filas"] if f["sub"] == "CAC-1"), None)
    check(f_ac and near(f_ac["cols"].get(2011), 700_000),
          f"tras % Ac=70: CMA · CAC-1 acueducto 2011 = 700.000 (obtenido {f_ac['cols'].get(2011) if f_ac else None})")
    # la clase 7 (CMO) NO cambia con el %
    cmo_ac = bv.resumen(conn, 1, "CMO", "acueducto")
    check(near(cmo_ac["total"].get(2011), 600_000), "CMO acueducto sigue 600.000 (clase 7 no usa el %)")

limpiar()
print()
if _fail:
    print(f"RESULTADO: {len(_fail)} fallo(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
