# -*- coding: utf-8 -*-
"""Cargue de factores de subsidio/contribución y del acuerdo del concejo, POR AÑO.

Los porcentajes (factores) de subsidio (−) y contribución (+) NO se derivan del formato
comercial: los fija el Concejo Municipal por anualidad mediante acuerdo (Ley 142 de 1994,
art. 89.1; límites Ley 1450 de 2011, art. 125). Este módulo captura, por VIGENCIA (año):

  · los factores por clase de uso y servicio  → tabla `factor_subsidio` (005_cargue.sql)
  · el acuerdo del concejo que los soporta     → tabla `acuerdo_subsidio` (039)

Se separa del balance FSRI (subsidios_service.py), que solo consume estos insumos.
"""
from sqlalchemy import text
from operacion_service import CLASES

# Clases con derecho a subsidio / sujetas a contribución (orientativo para el formulario).
SUBSIDIABLES = (1, 2, 3)
CONTRIBUYENTES = (5, 6, 10, 11)       # estratos 5/6, industrial, comercial

EXT_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}
MAX_BYTES = 25 * 1024 * 1024          # 25 MB


# ----------------------------------------------------------------- factores
def factores_por_anio(conn, empresa_id):
    """{vigencia: [filas]} con id, servicio, clase, factor_cargofijo, factor_consumo."""
    rows = conn.execute(text(
        "SELECT id, vigencia, servicio, clase, factor_cargofijo, factor_consumo "
        "FROM factor_subsidio WHERE empresa_id=:e ORDER BY vigencia DESC, servicio, clase"),
        {"e": empresa_id}).mappings().all()
    out = {}
    for r in rows:
        out.setdefault(r["vigencia"], []).append(dict(r))
    return out


def factor_guardar(conn, empresa_id, vigencia, servicio, clase, fcf, fcc, usuario_id):
    try:
        vig = int(vigencia)
    except (TypeError, ValueError):
        return None, "vigencia (año) inválida"
    serv = (servicio or "").strip()
    if serv not in ("acueducto", "alcantarillado"):
        return None, "servicio inválido"
    try:
        cl = int(clase)
    except (TypeError, ValueError):
        return None, "clase inválida"
    if cl not in CLASES:
        return None, "clase de uso no reconocida"
    fid = conn.execute(text(
        "INSERT INTO factor_subsidio(empresa_id,vigencia,servicio,clase,factor_cargofijo,factor_consumo) "
        "VALUES (:e,:v,:s,:c,:fcf,:fcc) "
        "ON CONFLICT (empresa_id,vigencia,servicio,clase) DO UPDATE SET "
        " factor_cargofijo=excluded.factor_cargofijo, factor_consumo=excluded.factor_consumo, "
        " cargado_en=now() RETURNING id"),
        {"e": empresa_id, "v": vig, "s": serv, "c": cl, "fcf": fcf, "fcc": fcc}).scalar()
    return fid, None


def factor_eliminar(conn, empresa_id, fid):
    conn.execute(text("DELETE FROM factor_subsidio WHERE empresa_id=:e AND id=:i"),
                 {"e": empresa_id, "i": fid})


# ----------------------------------------------------------------- acuerdo del concejo
def acuerdos_por_anio(conn, empresa_id):
    """{vigencia: fila} (sin el binario); incluye `tiene_soporte` y datos del acuerdo."""
    rows = conn.execute(text(
        "SELECT id, vigencia, numero_acuerdo, fecha_acuerdo, concejo, observacion, "
        "       soporte_nombre, soporte_tam, (soporte IS NOT NULL) AS tiene_soporte "
        "FROM acuerdo_subsidio WHERE empresa_id=:e ORDER BY vigencia DESC"),
        {"e": empresa_id}).mappings().all()
    return {r["vigencia"]: dict(r) for r in rows}


def acuerdo_guardar(conn, empresa_id, vigencia, d, soporte, usuario_id):
    """Alta/edición del acuerdo por vigencia. `soporte` = (nombre, tipo, tam, bytes) o None
    (si es None, conserva el documento que ya estuviera cargado)."""
    try:
        vig = int(vigencia)
    except (TypeError, ValueError):
        return None, "vigencia (año) inválida"
    p = {"e": empresa_id, "v": vig, "up": usuario_id,
         "num": (d.get("numero_acuerdo") or "").strip() or None,
         "fecha": _fecha(d.get("fecha_acuerdo")),
         "concejo": (d.get("concejo") or "").strip() or None,
         "obs": (d.get("observacion") or "").strip() or None}
    if soporte:
        p["sn"], p["st"], p["sz"], p["sb"] = soporte
        set_sop = (" soporte_nombre=:sn, soporte_tipo=:st, soporte_tam=:sz, soporte=:sb,")
        cols_sop = "soporte_nombre,soporte_tipo,soporte_tam,soporte,"
        vals_sop = ":sn,:st,:sz,:sb,"
    else:
        set_sop = ""
        cols_sop = ""
        vals_sop = ""
    aid = conn.execute(text(
        f"INSERT INTO acuerdo_subsidio(empresa_id,vigencia,numero_acuerdo,fecha_acuerdo,concejo,observacion,{cols_sop}cargado_por) "
        f"VALUES (:e,:v,:num,:fecha,:concejo,:obs,{vals_sop}:up) "
        f"ON CONFLICT (empresa_id,vigencia) DO UPDATE SET "
        f" numero_acuerdo=excluded.numero_acuerdo, fecha_acuerdo=excluded.fecha_acuerdo, "
        f" concejo=excluded.concejo, observacion=excluded.observacion,{set_sop} "
        f" cargado_por=excluded.cargado_por, cargado_en=now() RETURNING id"), p).scalar()
    return aid, None


def acuerdo_soporte(conn, empresa_id, vigencia):
    return conn.execute(text(
        "SELECT soporte_nombre AS nombre, soporte_tipo AS tipo, soporte AS contenido "
        "FROM acuerdo_subsidio WHERE empresa_id=:e AND vigencia=:v"),
        {"e": empresa_id, "v": vigencia}).mappings().first()


def acuerdo_eliminar(conn, empresa_id, vigencia):
    conn.execute(text("DELETE FROM acuerdo_subsidio WHERE empresa_id=:e AND vigencia=:v"),
                 {"e": empresa_id, "v": vigencia})


def estado_anio(conn, empresa_id, anio):
    """Para la validación: nº de factores cargados y si hay acuerdo (con/ sin soporte) en un año."""
    nf = conn.execute(text(
        "SELECT count(*) FROM factor_subsidio WHERE empresa_id=:e AND vigencia=:v"),
        {"e": empresa_id, "v": anio}).scalar() or 0
    ac = conn.execute(text(
        "SELECT numero_acuerdo, (soporte IS NOT NULL) AS tiene_soporte "
        "FROM acuerdo_subsidio WHERE empresa_id=:e AND vigencia=:v"),
        {"e": empresa_id, "v": anio}).mappings().first()
    return {"n_factores": nf, "acuerdo": bool(ac),
            "tiene_soporte": bool(ac and ac["tiene_soporte"]),
            "numero": ac["numero_acuerdo"] if ac else None}


def _fecha(s):
    if not s:
        return None
    s = str(s).strip()
    partes = s.split("-")
    try:
        if len(partes) == 2:
            return f"{int(partes[0]):04d}-{int(partes[1]):02d}-01"
        if len(partes) == 3:
            return f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
    except ValueError:
        return None
    return None
