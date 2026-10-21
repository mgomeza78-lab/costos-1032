# -*- coding: utf-8 -*-
"""Dashboard — resumen ejecutivo de indicadores por empresa.

Reúne, de las tablas que ya alimenta el sistema, los principales indicadores de la
empresa en una sola pantalla:

  - Costos económicos de referencia (CMA / CMO / CMI / CMICT)  — resultado_componente
  - Suscriptores y consumo facturado (último mes cargado)       — carga_mensual
  - Pérdidas: % (macromedición) e IPUF real                     — macromedicion / indicador_mensual
  - Tarifa vigente (cargo fijo y cargo por consumo)             — tarifa_vigente / base
  - Avance de inversiones (POIR)                                — proyecto/avance_inversion
  - Balance de subsidios y contribuciones (FSRI)                — subsidios_service

Cada bloque es defensivo: si falta el insumo, devuelve None y la vista lo muestra
como «sin datos», sin romper el tablero.
"""
from sqlalchemy import text
import inversiones_service as inv
import subsidios_service as sub


def _costos(conn, empresa_id):
    rows = conn.execute(text(
        "SELECT servicio, componente, valor, unidad FROM resultado_componente "
        "WHERE empresa_id=:e AND componente IN ('CMA','CMO','CMI','CMICT') "
        "ORDER BY servicio, componente"), {"e": empresa_id}).mappings().all()
    por = {}
    for r in rows:
        por.setdefault(r["servicio"], {})[r["componente"]] = r["valor"]
    return por


def _ultimo_mes(conn, empresa_id):
    r = conn.execute(text(
        "SELECT anio, mes FROM carga_mensual WHERE empresa_id=:e "
        "ORDER BY anio DESC, mes DESC LIMIT 1"), {"e": empresa_id}).first()
    if r:
        return r[0], r[1]
    r = conn.execute(text(
        "SELECT anio, mes FROM carga_mensual_detalle WHERE empresa_id=:e "
        "ORDER BY anio DESC, mes DESC LIMIT 1"), {"e": empresa_id}).first()
    return (r[0], r[1]) if r else (None, None)


def _comercial(conn, empresa_id, anio, mes):
    if anio is None:
        return None
    rows = conn.execute(text(
        "SELECT servicio, suscriptores, m3_facturados FROM carga_mensual "
        "WHERE empresa_id=:e AND anio=:a AND mes=:m ORDER BY servicio"),
        {"e": empresa_id, "a": anio, "m": mes}).mappings().all()
    if not rows:
        rows = conn.execute(text(
            "SELECT servicio, SUM(suscriptores) AS suscriptores, SUM(m3) AS m3_facturados "
            "FROM carga_mensual_detalle WHERE empresa_id=:e AND anio=:a AND mes=:m "
            "GROUP BY servicio ORDER BY servicio"),
            {"e": empresa_id, "a": anio, "m": mes}).mappings().all()
    if not rows:
        return None
    por = {r["servicio"]: {"suscriptores": r["suscriptores"], "m3": r["m3_facturados"]}
           for r in rows}
    tot_s = sum((r["suscriptores"] or 0) for r in rows)
    tot_m = sum((r["m3_facturados"] or 0.0) for r in rows)
    return {"anio": anio, "mes": mes, "por": por, "filas": [dict(r) for r in rows],
            "tot_susc": tot_s, "tot_m3": tot_m}


def _perdidas(conn, empresa_id, anio, mes):
    if anio is None:
        return None
    out = {"pct": None, "ipuf": None, "anio": anio, "mes": mes}
    try:
        prod = conn.execute(text(
            "SELECT COALESCE(SUM(m3_producido),0) FROM macromedicion "
            "WHERE empresa_id=:e AND anio=:a AND mes=:m AND servicio='acueducto'"),
            {"e": empresa_id, "a": anio, "m": mes}).scalar()
        fact = conn.execute(text(
            "SELECT m3_facturados FROM carga_mensual "
            "WHERE empresa_id=:e AND anio=:a AND mes=:m AND servicio='acueducto'"),
            {"e": empresa_id, "a": anio, "m": mes}).scalar()
        if prod and fact and prod > 0:
            out["pct"] = max(0.0, (prod - fact) / prod * 100.0)
    except Exception:
        pass
    try:
        out["ipuf"] = conn.execute(text(
            "SELECT ipuf_real FROM indicador_mensual "
            "WHERE empresa_id=:e AND anio=:a AND mes=:m AND servicio='acueducto'"),
            {"e": empresa_id, "a": anio, "m": mes}).scalar()
    except Exception:
        pass
    return out


def _tarifa(conn, empresa_id):
    rows = conn.execute(text(
        "SELECT DISTINCT ON (servicio) servicio, cargo_fijo, cargo_consumo, anio, mes "
        "FROM tarifa_vigente WHERE empresa_id=:e "
        "ORDER BY servicio, anio DESC, mes DESC"), {"e": empresa_id}).mappings().all()
    return {r["servicio"]: dict(r) for r in rows} if rows else {}


def resumen(conn, empresa_id):
    anio, mes = _ultimo_mes(conn, empresa_id)
    anios = sub.anios_disponibles(conn, empresa_id)
    anio_sub = anios[0] if anios else None
    bal = sub.balance(conn, empresa_id, anio_sub)
    try:
        poir = inv.resumen(conn, empresa_id)
    except Exception:
        poir = None
    return {
        "costos": _costos(conn, empresa_id),
        "comercial": _comercial(conn, empresa_id, anio, mes),
        "perdidas": _perdidas(conn, empresa_id, anio, mes),
        "tarifa": _tarifa(conn, empresa_id),
        "poir": poir,
        "subsidios": bal,
        "subsidios_anio": anio_sub,
    }
