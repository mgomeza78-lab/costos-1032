# -*- coding: utf-8 -*-
"""Balance de Subsidios y Contribuciones — Fondo de Solidaridad y Redistribución
de Ingresos (FSRI).

Replica la lógica del estudio de subsidios y contribuciones (el ejemplo de la APS
Neiva) a partir de lo que YA se carga mes a mes, sin pedir datos nuevos:

  - `carga_mensual_detalle` — comercial del SUI agregado por clase de uso
    (suscriptores, m³ facturados, m³ subsidiable). Fuente: Facturación 6080/6081.
  - `factor_subsidio`        — factores de subsidio (−) y contribución (+) por clase.
  - `tarifa_vigente`         — cargo fijo y cargo por consumo del mes (motor de
    indexación). Si un mes no la tiene, se usa como respaldo la tarifa base del
    período de inicio (resultado_componente: CMA y CMO+CMI+CMICT).

Convención de signos: subsidio negativo, contribución positiva.

Metodología (Ley 142 de 1994, arts. 89, 99 y 100; Ley 1450 de 2011, art. 125;
Decreto 1077 de 2015, art. 2.3.4.2.2):

  - Subsidio (estratos 1–3, factor de consumo negativo): se aplica al consumo
    BÁSICO (m³ subsidiable) y al cargo fijo cuando su factor es negativo.
  - Contribución (estratos 5 y 6, comercial e industrial, factores positivos): se
    aplica al consumo TOTAL y al cargo fijo.

Resultado por servicio (acueducto / alcantarillado) y total de la empresa:
subsidios otorgados, contribuciones recaudadas, balance (déficit si es negativo),
cobertura de subsidios con contribuciones, y déficit mensual promedio a cargo del
FSRI del municipio.
"""
from sqlalchemy import text
from operacion_service import CLASES, componentes_base

# Clases con derecho a subsidio (informativo para la vista).
ESTRATOS_SUBSIDIABLES = {1, 2, 3}


def _tarifas(conn, empresa_id):
    """{(anio, mes, servicio): (cargo_fijo, cargo_consumo)} desde tarifa_vigente."""
    rows = conn.execute(text(
        "SELECT anio, mes, servicio, cargo_fijo, cargo_consumo "
        "FROM tarifa_vigente WHERE empresa_id=:e"), {"e": empresa_id}).mappings().all()
    return {(r["anio"], r["mes"], r["servicio"]):
            (r["cargo_fijo"] or 0.0, r["cargo_consumo"] or 0.0) for r in rows}


def _factores(conn, empresa_id):
    """{(vigencia, servicio, clase): (factor_cargofijo, factor_consumo)}."""
    rows = conn.execute(text(
        "SELECT vigencia, servicio, clase, factor_cargofijo, factor_consumo "
        "FROM factor_subsidio WHERE empresa_id=:e"), {"e": empresa_id}).mappings().all()
    return {(r["vigencia"], r["servicio"], r["clase"]):
            (r["factor_cargofijo"] or 0.0, r["factor_consumo"] or 0.0) for r in rows}


def _tarifa_base(base, servicio):
    """Respaldo de tarifa (período de inicio) desde los componentes calculados."""
    b = base.get(servicio, {})
    cf = b.get("cma", 0.0) or 0.0
    cc = (b.get("cmo", 0.0) or 0.0) + (b.get("cmi", 0.0) or 0.0) + (b.get("cmict", 0.0) or 0.0)
    return cf, cc


def balance(conn, empresa_id, anio=None):
    """Calcula el balance de subsidios y contribuciones de la empresa.

    Si `anio` se indica, se limita a ese año; si no, toma todos los meses cargados.
    """
    base = componentes_base(conn, empresa_id)
    tar = _tarifas(conn, empresa_id)
    fac = _factores(conn, empresa_id)

    q = ("SELECT anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable "
         "FROM carga_mensual_detalle WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if anio:
        q += " AND anio=:a"
        p["a"] = anio
    rows = conn.execute(text(q), p).mappings().all()

    meses = set()
    tot = {}          # servicio -> {'sub', 'con'}
    por_clase = {}    # servicio -> clase -> fila agregada
    por_mes = {}      # (anio, mes) -> {'sub', 'con'}

    for r in rows:
        serv, clase = r["servicio"], r["clase"]
        a, m = r["anio"], r["mes"]
        meses.add((a, m))

        cf_cc = tar.get((a, m, serv))
        CF, CC = cf_cc if cf_cc else _tarifa_base(base, serv)
        fcf, fcc = fac.get((a, serv, clase), (0.0, 0.0))

        n = r["suscriptores"] or 0
        m3 = r["m3"] or 0.0
        m3s = r["m3_subsidiable"] or 0.0

        monto_cf = n * CF * fcf
        if fcc < 0:                      # subsidio: solo el consumo básico
            monto_cc = m3s * CC * fcc
        elif fcc > 0:                    # contribución: consumo total
            monto_cc = m3 * CC * fcc
        else:
            monto_cc = 0.0
        neto = monto_cf + monto_cc
        sub = neto if neto < 0 else 0.0
        con = neto if neto > 0 else 0.0

        t = tot.setdefault(serv, {"sub": 0.0, "con": 0.0})
        t["sub"] += sub
        t["con"] += con

        pc = por_clase.setdefault(serv, {}).setdefault(clase, {
            "clase": clase, "nombre": CLASES.get(clase, str(clase)),
            "n": 0, "m3": 0.0, "m3s": 0.0, "fcf": fcf, "fcc": fcc,
            "sub": 0.0, "con": 0.0})
        pc["n"] += n
        pc["m3"] += m3
        pc["m3s"] += m3s
        pc["fcf"], pc["fcc"] = fcf, fcc
        pc["sub"] += sub
        pc["con"] += con

        pm = por_mes.setdefault((a, m), {"sub": 0.0, "con": 0.0})
        pm["sub"] += sub
        pm["con"] += con

    n_meses = len(meses) or 1
    servicios = {}
    g_sub = g_con = 0.0
    for serv, t in tot.items():
        s, c = t["sub"], t["con"]
        servicios[serv] = {
            "subsidios": s,
            "contribuciones": c,
            "balance": s + c,
            "cobertura": (-c / s) if s else 0.0,
            "clases": sorted(por_clase.get(serv, {}).values(), key=lambda x: x["clase"]),
        }
        g_sub += s
        g_con += c

    total = {
        "subsidios": g_sub,
        "contribuciones": g_con,
        "balance": g_sub + g_con,
        "cobertura": (-g_con / g_sub) if g_sub else 0.0,
        "deficit_mensual": (g_sub + g_con) / n_meses,
        "superavit": (g_sub + g_con) > 0,
    }
    mensual = [{"anio": a, "mes": m, "subsidios": v["sub"], "contribuciones": v["con"],
                "balance": v["sub"] + v["con"]}
               for (a, m), v in sorted(por_mes.items())]

    return {"servicios": servicios, "total": total, "mensual": mensual,
            "meses": sorted(meses), "n_meses": n_meses, "anio": anio,
            "hay_datos": bool(rows)}


def anios_disponibles(conn, empresa_id):
    """Años con comercial cargado, para el selector de la vista."""
    rows = conn.execute(text(
        "SELECT DISTINCT anio FROM carga_mensual_detalle WHERE empresa_id=:e "
        "ORDER BY anio DESC"), {"e": empresa_id}).all()
    return [r[0] for r in rows]
