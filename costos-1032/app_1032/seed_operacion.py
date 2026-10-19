# -*- coding: utf-8 -*-
"""Semilla ILUSTRATIVA de la operación mensual (se ejecuta como el rol dueño).

Carga IPC+IPCs de ejemplo (jul–dic 2026), un detalle comercial por clase y factores de
subsidio/contribución de muestra para Las Ceibas, corre el motor de indexación (dos
canastas) y deriva la factura por estrato, para que el tablero quede demostrable.

IMPORTANTE: IPC/IPCs, detalle y factores aquí son ILUSTRATIVOS. En operación real provienen
del DANE (índices), del SUI/archivo propio (comercial) y del acuerdo municipal (factores).
"""
from sqlalchemy import text
from db import engine_owner
import operacion_service as ops

# IPC e IPCs (número índice) ilustrativos; el gatillo del 3 % dispara en nov-2026.
IPC = {(2026, 7): 100.000, (2026, 8): 100.800, (2026, 9): 101.500,
       (2026, 10): 102.300, (2026, 11): 103.100, (2026, 12): 103.700}

# Carga mensual agregada (gancho previo) para el tablero de tarifa vigente.
MUESTRA_LC = {"acueducto": {"susc": 112000, "m3": 1_950_000},
              "alcantarillado": {"susc": 108500, "m3": 1_780_000}}

# Detalle comercial por clase (acueducto) — valores de muestra basados en la base real.
DETALLE_AC = [
    # clase, suscriptores, m3, m3_subsidiable
    (1, 32739, 350910, 303641),
    (2, 63322, 702709, 598234),
    (3, 16227, 175998, 0),
    (5, 2600, 65000, 0),
    (6, 1500, 48000, 0),
    (11, 5800, 120400, 0),   # 11 = Comercial (código CLASEUSO del SUI)
]
# Factores de subsidio (-) / contribución (+) por clase (acueducto).
FACTORES_AC = {1: (-0.70, -0.70), 2: (-0.40, -0.40), 3: (-0.15, -0.15),
               5: (0.50, 0.50), 6: (0.60, 0.60), 11: (0.50, 0.50)}


def main():
    with engine_owner.begin() as c:
        for t in ("indice_ipc", "tarifa_vigente", "carga_mensual", "carga_mensual_detalle",
                  "factor_subsidio", "indicador_mensual", "factura_clase"):
            c.execute(text(f"DELETE FROM {t}"))
        for (a, m), v in IPC.items():
            c.execute(text("INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) "
                           "VALUES (:a,:m,:v,:v,'DANE (ilustrativo)','supuesto')"),
                      {"a": a, "m": m, "v": v})
        lc = c.execute(text("SELECT id FROM empresa WHERE codigo='LAS_CEIBAS'")).scalar_one()
        for (a, m) in ops.PERIODOS:
            # agregado (tablero de tarifa vigente)
            for serv, d in MUESTRA_LC.items():
                c.execute(text("INSERT INTO carga_mensual(empresa_id,anio,mes,servicio,"
                               "suscriptores,m3_facturados,origen) VALUES (:e,:a,:m,:s,:su,:m3,'muestra')"),
                          {"e": lc, "a": a, "m": m, "s": serv, "su": d["susc"], "m3": d["m3"]})
            # detalle por clase (acueducto)
            for (clase, su, m3, m3s) in DETALLE_AC:
                c.execute(text("INSERT INTO carga_mensual_detalle(empresa_id,anio,mes,servicio,"
                               "clase,suscriptores,m3,m3_subsidiable,origen) "
                               "VALUES (:e,:a,:m,'acueducto',:c,:su,:m3,:ms,'muestra')"),
                          {"e": lc, "a": a, "m": m, "c": clase, "su": su, "m3": m3, "ms": m3s})
        # factores (vigencia 2026, acueducto)
        for clase, (fcf, fc) in FACTORES_AC.items():
            c.execute(text("INSERT INTO factor_subsidio(empresa_id,vigencia,servicio,clase,"
                           "factor_cargofijo,factor_consumo) VALUES (:e,2026,'acueducto',:c,:fcf,:fc)"),
                      {"e": lc, "c": clase, "fcf": fcf, "fc": fc})
        # motor + factura para las 3 empresas
        total_ix = total_fac = 0
        for e in c.execute(text("SELECT id, codigo FROM empresa ORDER BY id")).mappings().all():
            filas, ix = ops.procesar_empresa(c, e["id"])
            fac = ops.derivar_factura(c, e["id"])
            total_ix += ix; total_fac += fac
            print(f"  {e['codigo']:12} tarifa: {filas} filas, {ix} indexaciones; factura: {fac} filas")
    print(f"Semilla de operación lista. Indexaciones: {total_ix}; filas de factura por estrato: {total_fac}.")


if __name__ == "__main__":
    main()
