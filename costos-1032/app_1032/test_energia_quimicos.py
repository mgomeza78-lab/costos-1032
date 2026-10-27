# -*- coding: utf-8 -*-
"""Pruebas del cálculo de costos particulares de ENERGÍA (CE) e INSUMOS QUÍMICOS (CIQ).

Valida la fórmula del art. 2.1.2.1.3.4.6 contra valores calculados a mano (independientes),
con los dos tipos de energía del modelo (bombeo con fórmula hidráulica; otros procesos = Ko·Pce),
y el round-trip por la base: insertar puntos/insumos y que `totales` sume CE/CIQ por servicio/año.
Usa el año ficticio 2011 en Las Ceibas (empresa 1) y limpia al final.
"""
from sqlalchemy import text
import db, energia_quimicos_service as eq

_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def near(a, b, t=1.0):
    return a is not None and abs(a - b) <= t


# ---------------- 1) Unidad: fórmula de energía y químicos ----------------
print("== cálculo CE (bombeo + otros) y CIQ ==")
# Bombeo acueducto (fila 6 ESSMAR): V=57688, H=65, Kr=62004, Pce=1000.88 -> η=0.63 (V≤1e6), Υ=9.8
b = eq.calc_energia_punto({"servicio": "acueducto", "tipo": "bombeo", "volumen_m3": 57688,
                           "altura_m": 65, "consumo_real_kwh": 62004, "precio_kwh": 1000.88})
check(near(b["eta"], 0.63) and near(b["keb"], 16202.4938, 0.01), f"bombeo: η=0.63, Keb≈16.202 (obtenido η={b['eta']}, Keb={b['keb']:.2f})")
check(near(b["ceb"], 16216752.02, 1.0), f"bombeo: Ceb≈16.216.752 (obtenido {b['ceb']:.2f})")
# η por volumen: >3.000.000 -> 0.77 ; 1-3M -> 0.69
check(near(eq.eta_de("acueducto", 5_000_000), 0.77) and near(eq.eta_de("acueducto", 2_000_000), 0.69)
      and near(eq.eta_de("alcantarillado", 5_000_000), 0.60), "η por rango de volumen (0.69/0.77) y alcantarillado 0.60")
# Otros procesos (fila 190): Ko=98085, Pce=1011.4717 -> Ce = Ko·Pce (sin eficiencia)
o = eq.calc_energia_punto({"servicio": "acueducto", "tipo": "otros",
                           "consumo_real_kwh": 98085, "precio_kwh": 1011.471723505123})
check(near(o["ceb"], 99210204.0, 1.0) and o["castigo"] == 0.0, f"otros procesos: Ce=Ko·Pce≈99.210.204 (obtenido {o['ceb']:.2f})")
# Químico (fila 5): precio 2225.3 × Σ(12 meses=113.750) = 253.127.875
q = eq.calc_quimico_item({"precio_kg": 2225.3, "m1": 12750, "m2": 14750, "m3": 12250, "m4": 8500,
                          "m5": 10250, "m6": 6250, "m7": 8750, "m8": 8500, "m9": 9000, "m10": 9000,
                          "m11": 7000, "m12": 6750})
check(near(q["cantidad_anual"], 113750) and near(q["ciq"], 253127875.0, 1.0),
      f"químico: cantidad 113.750 kg, CIQ≈253.127.875 (obtenido {q['ciq']:.2f})")

# ---------------- 2) Round-trip por la base: totales por servicio/año ----------------
print("\n== round-trip: insertar y que `totales` sume CE/CIQ por servicio ==")
AN = 2011


def limpiar():
    with db.engine_owner.begin() as c:
        c.execute(text("DELETE FROM energia_punto WHERE empresa_id=1 AND anio=:a"), {"a": AN})
        c.execute(text("DELETE FROM quimico_item WHERE empresa_id=1 AND anio=:a"), {"a": AN})


limpiar()
with db.engine_owner.begin() as c:
    c.execute(text("INSERT INTO energia_punto(empresa_id,anio,servicio,tipo,punto,volumen_m3,altura_m,"
                   "consumo_real_kwh,precio_kwh) VALUES (1,:a,'acueducto','bombeo','P1',57688,65,62004,1000.88)"), {"a": AN})
    c.execute(text("INSERT INTO energia_punto(empresa_id,anio,servicio,tipo,punto,consumo_real_kwh,precio_kwh) "
                   "VALUES (1,:a,'acueducto','otros','PTAP',98085,1011.471723505123)"), {"a": AN})
    c.execute(text("INSERT INTO quimico_item(empresa_id,anio,servicio,punto,insumo,precio_kg,"
                   "m1,m2,m3,m4,m5,m6,m7,m8,m9,m10,m11,m12) "
                   "VALUES (1,:a,'acueducto','PTAP','Hipoclorito',2225.3,12750,14750,12250,8500,10250,6250,8750,8500,9000,9000,7000,6750)"), {"a": AN})

with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    t = eq.totales(conn, 1, anio=AN)
    ce = t["ce"].get(("acueducto", AN), {})
    ciq = t["ciq"].get(("acueducto", AN), {})
    check(near(ce.get("ce"), 16216752.02 + 99210204.0, 2.0),
          f"CE acueducto = bombeo + otros ≈ 115.426.956 (obtenido {ce.get('ce'):.2f})")
    check(near(ciq.get("ciq"), 253127875.0, 1.0), f"CIQ acueducto ≈ 253.127.875 (obtenido {ciq.get('ciq'):.2f})")
    ce_v, ciq_v = eq.ce_ciq_de(conn, 1, "acueducto", AN)
    check(near(ce_v, 115426956.02, 2.0) and near(ciq_v, 253127875.0, 1.0), "ce_ciq_de devuelve CE/CIQ del servicio")
    ce_al, ciq_al = eq.ce_ciq_de(conn, 1, "alcantarillado", AN)
    check(ce_al is None and ciq_al is None, "ce_ciq_de devuelve (None, None) si no hay módulo cargado para ese servicio")

limpiar()

# ---------------- 3) Integración al motor: el CMO usa el CE del módulo ----------------
print("\n== integración al motor: el CE reconocido del módulo entra al CMO (reemplaza el contable) ==")
import recalculo_service as rc
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    rc.recalcular(conn, 1)
    fila = conn.execute(text("SELECT anio, mes, cmo_mes FROM costo_referencia_mensual WHERE empresa_id=1 "
                             "AND servicio='acueducto' ORDER BY anio, mes LIMIT 1")).mappings().first()
    if fila:
        base_cmo = fila["cmo_mes"] or 0.0
        by = fila["anio"] - 2                              # año base del CMO (i-2)
        conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=1 AND anio=:a"), {"a": by})
        conn.execute(text("INSERT INTO energia_punto(empresa_id,anio,servicio,tipo,punto,consumo_real_kwh,"
                          "precio_kwh) VALUES (1,:a,'acueducto','otros','PTAP',1000000,5000)"), {"a": by})
        rc.recalcular(conn, 1)
        nuevo = conn.execute(text("SELECT cmo_mes FROM costo_referencia_mensual WHERE empresa_id=1 "
                                  "AND servicio='acueducto' ORDER BY anio, mes LIMIT 1")).scalar() or 0.0
        check(abs(nuevo - base_cmo) > 0.01, f"el CMO cambia al cargar energía del año base (de {base_cmo:.2f} a {nuevo:.2f})")
        conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=1 AND anio=:a"), {"a": by})
        rc.recalcular(conn, 1)                             # restaurar el estado de la semilla
    else:
        check(True, "sin escenario de recálculo sembrado; se omite la integración (OK)")

print()
if _fail:
    print(f"RESULTADO: {len(_fail)} fallo(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
