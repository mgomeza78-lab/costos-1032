# -*- coding: utf-8 -*-
"""Pruebas de la desagregación del comercial por APS (cod_dane) en el período de inicio.

  · reporte SUI con columna de municipio/DANE → detalle por (clase, APS) y resumen conjunto (total);
  · el TOTAL para costos = Σ de las APS (como lo lee recalculo con GROUP BY servicio,anio,mes);
  · reporte SUI sin municipio → todo al conjunto ('') (compatibilidad hacia atrás);
  · CSV comercial propio con columna `aps`;
  · re-cargue del mismo mes sin municipio no deja filas huérfanas por APS (reemplazo limpio);
  · derivar_factura agrega el detalle por clase sumando las APS (una sola fila por clase).

Usa el año sintético 2099 (ninguna siembra ni período tarifario lo toca) y limpia al final.
"""
from sqlalchemy import text
import config, main, db
import ingesta
import operacion_service as ops

EID = 1          # Las Ceibas (Neiva 41001 + Palermo 41524)
A = 2099
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def _clean():
    with db.engine_owner.begin() as cn:
        for t in ("factura_clase", "carga_mensual_detalle", "carga_mensual", "tarifa_vigente", "numerador_mensual"):
            cn.execute(text(f"DELETE FROM {t} WHERE empresa_id=:e AND anio=:a"), {"e": EID, "a": A})


_clean()

# --- Reporte SUI de acueducto CON municipio/DANE (una fila por suscriptor) ---
sui_muni = (
    "CLASEUSO,LECT_CONSUMO,CONS_SUB,DIVIPOLA\n"
    "1,20,20,41001\n"
    "1,20,20,41001\n"      # clase 1, Neiva: 2 susc, 40 m3
    "5,30,0,41524\n"
    "5,30,0,41524\n"       # clase 5, Palermo: 2 susc, 60 m3
    "5,30,0,41001\n"       # clase 5, Neiva: 1 susc, 30 m3
)
print("== SUI con municipio → detalle por (clase, APS) + resumen conjunto ==")
with db.scope_conn({"allow_all": True}) as cn:
    ok, err = ingesta.cargar_facturacion_sui(cn, EID, "acueducto", A, 7, sui_muni)
check(ok == 3 and not err, f"3 combinaciones (clase,APS) cargadas sin error ({ok}, {err})")

with db.engine_owner.connect() as cn:
    det = {(r["clase"], r["cod_dane"]): (r["suscriptores"], r["m3"]) for r in cn.execute(text(
        "SELECT clase, cod_dane, suscriptores, m3 FROM carga_mensual_detalle "
        "WHERE empresa_id=:e AND anio=:a AND mes=7 AND servicio='acueducto'"), {"e": EID, "a": A}).mappings()}
    res = cn.execute(text("SELECT cod_dane, suscriptores, m3_facturados FROM carga_mensual "
        "WHERE empresa_id=:e AND anio=:a AND mes=7 AND servicio='acueducto'"),
        {"e": EID, "a": A}).mappings().all()
    # Lo que lee recalculo para el total (suma sobre APS):
    tot = cn.execute(text("SELECT COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3),0) af "
        "FROM carga_mensual_detalle WHERE empresa_id=:e AND anio=:a AND mes=7 AND servicio='acueducto'"),
        {"e": EID, "a": A}).mappings().first()
check(det.get((1, "41001")) == (2, 40.0), f"clase 1 · Neiva = 2 susc/40 m³ ({det.get((1,'41001'))})")
check(det.get((5, "41524")) == (2, 60.0), f"clase 5 · Palermo = 2 susc/60 m³ ({det.get((5,'41524'))})")
check(det.get((5, "41001")) == (1, 30.0), f"clase 5 · Neiva = 1 susc/30 m³ ({det.get((5,'41001'))})")
check(len(res) == 1 and res[0]["cod_dane"] == "" and res[0]["suscriptores"] == 5 and abs(res[0]["m3_facturados"] - 130.0) < 1e-6,
      f"resumen conjunto (1 fila '') = 5 susc/130 m³ ({[dict(r) for r in res]})")
check(tot["n"] == 5 and abs(tot["af"] - 130.0) < 1e-6, f"TOTAL para costos = Σ APS = 5 susc/130 m³ ({dict(tot)})")

print("== derivar_factura agrega por clase sumando APS (una fila por clase) ==")
with db.engine_owner.begin() as cn:
    cn.execute(text("INSERT INTO tarifa_vigente(empresa_id,anio,mes,servicio,cargo_fijo,cargo_consumo,"
        "factor_acumulado,variacion_acum,indexado,var_ipc,indexado_ipc) "
        "VALUES (:e,:a,7,'acueducto',1000,100,1,0,false,0,false) "
        "ON CONFLICT (empresa_id,anio,mes,servicio) DO NOTHING"), {"e": EID, "a": A})
with db.scope_conn({"allow_all": True}) as cn:
    ops.derivar_factura(cn, EID)
with db.engine_owner.connect() as cn:
    fc = {r["clase"]: r["suscriptores"] for r in cn.execute(text(
        "SELECT clase, suscriptores FROM factura_clase WHERE empresa_id=:e AND anio=:a AND mes=7 "
        "AND servicio='acueducto'"), {"e": EID, "a": A}).mappings()}
check(fc.get(5) == 3, f"factura clase 5 = 3 susc (Neiva 1 + Palermo 2, una sola fila) ({fc.get(5)})")
check(fc.get(1) == 2, f"factura clase 1 = 2 susc ({fc.get(1)})")

print("== Re-cargue del mismo mes SIN municipio → reemplazo limpio (sin huérfanas por APS) ==")
sui_sin = ("CLASEUSO,LECT_CONSUMO,CONS_SUB\n" "1,20,20\n" "1,20,20\n" "5,30,0\n")
with db.scope_conn({"allow_all": True}) as cn:
    ingesta.cargar_facturacion_sui(cn, EID, "acueducto", A, 7, sui_sin)
with db.engine_owner.connect() as cn:
    danes = cn.execute(text("SELECT DISTINCT cod_dane FROM carga_mensual_detalle "
        "WHERE empresa_id=:e AND anio=:a AND mes=7 AND servicio='acueducto'"),
        {"e": EID, "a": A}).scalars().all()
check(danes == [""], f"tras re-cargar sin municipio solo queda el conjunto '' (sin 41001/41524) ({danes})")

print("== CSV comercial propio con columna aps ==")
csv_aps = ("anio,mes,servicio,clase,suscriptores,m3,m3_subsidiable,aps\n"
           f"{A},8,acueducto,1,100,2000,2000,Neiva\n"
           f"{A},8,acueducto,1,50,1000,1000,Palermo\n")
with db.scope_conn({"allow_all": True}) as cn:
    ok2, err2 = ingesta.cargar_comercial(cn, EID, csv_aps)
with db.engine_owner.connect() as cn:
    d2 = {r["cod_dane"]: r["suscriptores"] for r in cn.execute(text(
        "SELECT cod_dane, suscriptores FROM carga_mensual_detalle "
        "WHERE empresa_id=:e AND anio=:a AND mes=8 AND servicio='acueducto'"), {"e": EID, "a": A}).mappings()}
check(ok2 == 2 and d2.get("41001") == 100 and d2.get("41524") == 50,
      f"CSV propio repartió por APS (Neiva 100, Palermo 50) ({d2})")

print("== Vista Cargado por APS (ruta) ==")
import re
from starlette.testclient import TestClient
cli = TestClient(main.app)
m = re.search(r'name="csrf-token" content="([^"]+)"', cli.get("/login").text)
cli.post("/login", data={"email": "mgomeza78@gmail.com", "password": config.SEED_PASSWORD,
                         "csrf": (m.group(1) if m else "")}, follow_redirects=False)
html = cli.get(f"/empresa/{EID}/cargar?fuente=comercial&cmvista=aps&cmanio={A}").text
check("Por APS" in html and ("Neiva" in html or "Palermo" in html), "la vista 'Por APS' lista municipios")

# ---------------- Balance por APS (numerador_mensual) ----------------
import recalculo_service as rc
NUMS = {"CACe": 1000.0, "COCe_comparables": 2000.0}   # claves del clasificador
SPLIT = {"CACe": 1.0, "COCe": 1.0}                     # todo acueducto (para la prueba)
print("== Balance conjunto (por defecto) → cod_dane='' ==")
with db.scope_conn({"allow_all": True}) as cn:
    ingesta.persistir_numeradores_mensual(cn, EID, A, 9, NUMS, SPLIT, cod_dane="")
with db.engine_owner.connect() as cn:
    danes0 = cn.execute(text("SELECT DISTINCT cod_dane FROM numerador_mensual "
        "WHERE empresa_id=:e AND anio=:a AND mes=9"), {"e": EID, "a": A}).scalars().all()
check(danes0 == [""], f"balance conjunto guarda solo '' ({danes0})")

print("== Balance por APS: cargar un APS borra el conjunto; dos APS suman el total ==")
with db.scope_conn({"allow_all": True}) as cn:
    ingesta.persistir_numeradores_mensual(cn, EID, A, 9, NUMS, SPLIT, cod_dane="41001")
    ingesta.persistir_numeradores_mensual(cn, EID, A, 9, NUMS, SPLIT, cod_dane="41524")
with db.engine_owner.connect() as cn:
    danes1 = sorted(cn.execute(text("SELECT DISTINCT cod_dane FROM numerador_mensual "
        "WHERE empresa_id=:e AND anio=:a AND mes=9"), {"e": EID, "a": A}).scalars().all())
    tot_cace = rc._num_mes(cn, EID).get(("acueducto", A, 9), {}).get("CACe")
check(danes1 == ["41001", "41524"], f"tras cargar dos APS el conjunto se fue; quedan 41001 y 41524 ({danes1})")
check(tot_cace == 2000.0, f"el total del mes (recálculo) = Σ APS = 1000+1000 = 2000 ({tot_cace})")

print("== Recargar el conjunto reemplaza a las APS ==")
with db.scope_conn({"allow_all": True}) as cn:
    ingesta.persistir_numeradores_mensual(cn, EID, A, 9, NUMS, SPLIT, cod_dane="")
with db.engine_owner.connect() as cn:
    danes2 = cn.execute(text("SELECT DISTINCT cod_dane FROM numerador_mensual "
        "WHERE empresa_id=:e AND anio=:a AND mes=9"), {"e": EID, "a": A}).scalars().all()
    tot_cace2 = rc._num_mes(cn, EID).get(("acueducto", A, 9), {}).get("CACe")
check(danes2 == [""], f"recargar el conjunto deja solo '' ({danes2})")
check(tot_cace2 == 1000.0, f"total vuelve a 1000 (un solo balance conjunto) ({tot_cace2})")

_clean()
print("\n" + ("TODAS LAS PRUEBAS DE COMERCIAL/BALANCE POR APS PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
