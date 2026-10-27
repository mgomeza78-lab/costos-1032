# -*- coding: utf-8 -*-
"""Pruebas del balance de prueba por SUBCOMPONENTE, detalle por cuenta y reparto por servicio:

  · clasificar_detalle: clase 5 a 'repartir' (por %), clase 7 por el servicio de la cuenta, + detalle;
  · cargar un balance (año base) guarda numerador_subcomp y numerador_cuenta sin tocar el motor (<2026);
  · balance_view.resumen: por año Ac / Al / Ac+Al, drill-down de cuentas y tabla de Excluidos;
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


# ---------------- 1) Unidad: cubetas + detalle + reparto ----------------
print("== clasificar_detalle + aplicar_pct (clase 5 por %, clase 7 por cuenta) ==")
cat = {
    "51010101": ("CAC-1", "CMA", "", ""),               # clase 5 -> reparte por %
    "750201":   ("COC-2", "CMO", "", "acueducto"),      # clase 7 -> acueducto
    "7503040":  ("COC-2", "CMO", "", "alcantarillado"),  # clase 7 -> alcantarillado
}
filas = [
    {"codigo_norm": "51010101", "nombre": "SUELDOS", "saldo_final": 1_000_000.0},
    {"codigo_norm": "750201",   "nombre": "OPER AC", "saldo_final": 600_000.0},
    {"codigo_norm": "75030401", "nombre": "OPER AL", "saldo_final": 400_000.0},  # usa prefijo 7503040
]
buckets, cuentas, sin = clf.clasificar_detalle(filas, cat)
check(near(buckets[("CMA", "CAC-1")]["repartir"], 1_000_000), "CAC-1 (clase 5) va a 'repartir'")
check(near(buckets[("CMO", "COC-2")]["ac_dir"], 600_000) and near(buckets[("CMO", "COC-2")]["al_dir"], 400_000),
      "COC-2 (clase 7): 600k acueducto + 400k alcantarillado directos")
check(len(cuentas) == 3 and any(c["codigo"] == "51010101" and near(c["repartir"], 1_000_000) for c in cuentas),
      "clasificar_detalle devuelve 3 cuentas con su cubeta")
agg = clf.aplicar_pct(buckets, 0.6)
check(near(agg[("CMA", "CAC-1", "acueducto")], 600_000) and near(agg[("CMA", "CAC-1", "alcantarillado")], 400_000),
      "CAC-1 repartido 60/40 = 600k/400k")

# ---------------- 2) Carga del balance (año base) + vista ----------------
print("\n== carga de balance año base (2011) → vista por año Ac/Al/Ac+Al + detalle + excluidos ==")
balance_csv = ("CODIGO,NOMBRE,SALDO INICIAL,DEBITO,CREDITO,SALDO FINAL\n"
               "51010101,SUELDOS DE PERSONAL,0,0,0,1000000\n"
               "750201,COSTOS GENERALES OPER,0,0,0,600000\n"
               "75030401,COSTOS OPER ALCANT,0,0,0,400000\n"
               "75111708,ALUMBRADO PUBLICO,0,0,0,200000\n"      # ICTA (clase 5) -> reparte por %
               "511154,ORGANIZACION DE EVENTOS,0,0,0,50000\n")  # EXCLUIDO (no reconocido)


def limpiar():
    with db.engine_owner.begin() as c:
        c.execute(text("DELETE FROM numerador_subcomp WHERE empresa_id=1 AND anio=2011"))
        c.execute(text("DELETE FROM numerador_cuenta WHERE empresa_id=1 AND anio=2011"))
        c.execute(text("DELETE FROM balance_reparto WHERE empresa_id=1"))
        c.execute(text("DELETE FROM balance_ajuste WHERE empresa_id=1 AND anio=2011"))
        c.execute(text("DELETE FROM balance_cargue WHERE empresa_id=1 AND anio=2011"))


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
    r = bv.resumen(conn, 1, "CMA")        # pct default 0.52
    check(2011 in r["anios"], "la vista lista el año 2011 cargado")
    cac1 = next((f for f in r["principal"]["filas"] if f["sub"] == "CAC-1"), None)
    cell = cac1["cols"][2011] if cac1 else {}
    check(near(cell.get("suma"), 1_000_000), f"CMA·CAC-1 Ac+Al 2011 = 1.000.000 (obtenido {cell.get('suma')})")
    check(near(cell.get("ac"), 520_000), f"CMA·CAC-1 Ac 2011 = 520.000 (52%) (obtenido {cell.get('ac')})")
    check(near(cell.get("al"), 480_000), f"CMA·CAC-1 Al 2011 = 480.000 (48%) (obtenido {cell.get('al')})")
    det = next((d for d in (cac1["detalle"] if cac1 else []) if d["codigo"] == "51010101"), None)
    check(det and near(det["cols"][2011]["ac"], 520_000),
          "drill-down: la cuenta 51010101 aparece en el detalle de CAC-1 con Ac = 520.000")
    cmo = bv.resumen(conn, 1, "CMO")
    tc = cmo["principal"]["total"].get(2011, {})
    check(near(tc.get("ac"), 600_000) and near(tc.get("al"), 400_000),
          f"CMO total 2011: Ac 600k (7502) / Al 400k (7503) (obtenido ac={tc.get('ac')} al={tc.get('al')})")
    check(r["excluido"]["hay"] and any(f["sub"].endswith("-X") or f["sub"] in ("CAC-X",) for f in r["excluido"]["filas"]),
          "la tabla de Excluidos tiene la cuenta no reconocida (511154)")

# ---------------- 3) Cambiar el % re-reparte la clase 5 ----------------
print("\n== cambiar el % de reparto re-reparte la clase 5 ==")
c.post("/empresa/1/balance-reparto",
       data={"pct_ac": "70", "comp": "CMA", "csrf": tok("/empresa/1/balance?comp=CMA")},
       follow_redirects=False)
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    r = bv.resumen(conn, 1, "CMA")
    cac1 = next((f for f in r["principal"]["filas"] if f["sub"] == "CAC-1"), None)
    check(cac1 and near(cac1["cols"][2011]["ac"], 700_000),
          f"tras % Ac=70: CMA·CAC-1 Ac 2011 = 700.000 (obtenido {cac1['cols'][2011]['ac'] if cac1 else None})")
    cmo = bv.resumen(conn, 1, "CMO")
    check(near(cmo["principal"]["total"][2011]["ac"], 600_000), "CMO Ac sigue 600.000 (clase 7 no usa el %)")

# ---------------- 4) Ajustes manuales: desagregación CAC-5 (informativa) + exclusión (se resta) ----------------
print("\n== desagregaciones CAC-4/5/6 (informativas) + exclusión explícita (se resta del numerador) ==")
# % Ac quedó en 0,70 tras la sección 3; el bruto del CMA 2011 = CAC-1 1.000.000 => Ac 700k / Al 300k.
c.post("/empresa/1/balance-ajuste",
       data={"anio": 2011, "tipo": "CAC-5", "concepto": "Esquemas diferenciales urbanos (lit. a)",
             "servicio": "acueducto", "valor": "100000", "csrf": tok("/empresa/1/cargar?fuente=balance"), "next": ""},
       follow_redirects=False)
c.post("/empresa/1/balance-ajuste",
       data={"anio": 2011, "tipo": "exclusion", "componente": "CMA", "concepto": "Donaciones",
             "servicio": "acueducto", "valor": "50000", "csrf": tok("/empresa/1/cargar?fuente=balance"), "next": ""},
       follow_redirects=False)
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    r = bv.resumen(conn, 1, "CMA")
    des = r["desagregacion"]
    check(des["hay"] and len(des["filas"]) == 3, f"desagregación muestra las 3 filas CAC-4/5/6 (obtenido {len(des['filas'])})")
    cac5 = next((f for f in des["filas"] if f["sub"] == "CAC-5"), None)
    check(cac5 and near(cac5["cols"][2011]["ac"], 100_000),
          f"CAC-5 (informativa) Ac 2011 = 100.000 (obtenido {cac5['cols'][2011]['ac'] if cac5 else None})")
    check(near(r["principal"]["total"][2011]["suma"], 1_000_000),
          f"el bruto del CMA NO cambia por la desagregación (sigue 1.000.000, obtenido {r['principal']['total'][2011]['suma']})")
    exc = r["exclusiones"]
    check(exc["hay"] and near(exc["total"][2011]["ac"], 50_000),
          f"exclusión 'Donaciones' Ac 2011 = 50.000 (obtenido {exc['total'][2011]['ac']})")
    check(near(r["neto"][2011]["ac"], 650_000) and near(r["neto"][2011]["suma"], 950_000),
          f"neto = bruto − exclusión: Ac 700k−50k=650k, suma 1.000.000−50.000=950.000 "
          f"(obtenido ac={r['neto'][2011]['ac']} suma={r['neto'][2011]['suma']})")
    # La exclusión del CMA no afecta el neto de otro componente.
    rcmo = bv.resumen(conn, 1, "CMO")
    check(near(rcmo["exclusiones"]["total"].get(2011, {}).get("suma", 0.0), 0.0),
          "la exclusión cargada en CMA no aparece en las exclusiones del CMO")

# ---------------- 5) Registro de cargues: archivo + período + totales de control clase 5/7 ----------------
print("\n== registro de balances cargados (archivo, período, totales clase 5/7) + borrado por archivo ==")
# El balance de la sección 2 se cargó como 'bal2011.csv' (ene–dic). Totales de control por clase PUC
# (cuentas hoja): clase 5 = 51010101 (1.000.000) + 511154 (50.000) = 1.050.000;
# clase 7 = 750201 (600.000) + 75030401 (400.000) + 75111708 (200.000) = 1.200.000.
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    cg = bv.cargues(conn, 1)
    row = next((z for z in cg if z["anio"] == 2011), None)
    check(row is not None and row["archivo"] == "bal2011.csv",
          f"el cargue 2011 aparece con su nombre de archivo (obtenido {row['archivo'] if row else None})")
    check(row and near(row["total5"], 1_050_000),
          f"total cuenta 5 = 1.050.000 (obtenido {row['total5'] if row else None})")
    check(row and near(row["total7"], 1_200_000),
          f"total cuenta 7 = 1.200.000 (obtenido {row['total7'] if row else None})")
    check(row and row["mes_ini"] == 1 and row["mes_fin"] == 12, "el período del cargue 2011 es ene–dic")
r = c.post("/empresa/1/balance-cargue-eliminar",
           data={"anio": 2011, "cod_dane": "", "csrf": tok("/empresa/1/cargar?fuente=balance"), "next": ""},
           follow_redirects=False)
check(r.status_code in (302, 303), "borrar el cargue por archivo/año redirige")
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    cg2 = bv.cargues(conn, 1)
    check(not any(z["anio"] == 2011 for z in cg2), "tras borrar, el año 2011 ya no está en el registro de cargues")
    # El borrado quita la clasificación del balance (subcomponentes y detalle); los ajustes manuales
    # de la sección 4 son independientes y se conservan (por eso 2011 sigue en la lista de años).
    left = conn.execute(text("SELECT count(*) FROM numerador_subcomp WHERE empresa_id=1 AND anio=2011")).scalar()
    lcta = conn.execute(text("SELECT count(*) FROM numerador_cuenta WHERE empresa_id=1 AND anio=2011")).scalar()
    check(left == 0 and lcta == 0, f"tras borrar, no quedan subcomponentes ni cuentas del balance 2011 (obtenido {left}/{lcta})")

limpiar()
print()
if _fail:
    print(f"RESULTADO: {len(_fail)} fallo(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
