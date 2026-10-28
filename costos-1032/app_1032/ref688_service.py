# -*- coding: utf-8 -*-
"""Último costo de referencia del marco 688 — punto de partida del período de inicio.

Captura, por servicio, la última tarifa / costo económico de referencia que la empresa
venía aplicando bajo la metodología anterior (Res. CRA 688/2014) y la fecha a la que
estaban indexados esos valores (art. 2.1.2.1.1.8 de la Res. CRA 1032/2026). Es un insumo
EXCLUSIVO del período de inicio: sirve de referencia para la transición y la comparación
con los costos económicos calculados bajo la nueva metodología. No se inventan valores:
los aporta la empresa a partir del último acto administrativo con que aplicó el marco 688.
"""
from sqlalchemy import text

SERVICIOS = {"acueducto": "Acueducto", "alcantarillado": "Alcantarillado"}

_CAMPOS_NUM = ("cargo_fijo", "cargo_consumo", "cma", "cmo", "cmi", "cmict", "indice_base")
_CAMPOS_TXT = ("acto_admin", "observacion", "origen")


def lista(conn, empresa_id):
    """Filas crudas por servicio (orden acueducto, alcantarillado)."""
    return conn.execute(text(
        "SELECT id, servicio, cargo_fijo, cargo_consumo, cma, cmo, cmi, cmict, "
        "       fecha_indexacion, indice_base, acto_admin, observacion, origen "
        "FROM costo_referencia_688 WHERE empresa_id=:e ORDER BY servicio"),
        {"e": empresa_id}).mappings().all()


def por_servicio(conn, empresa_id):
    """{servicio: fila} para precargar el formulario."""
    return {r["servicio"]: dict(r) for r in lista(conn, empresa_id)}


def guardar(conn, empresa_id, servicio, d, usuario_id):
    serv = (servicio or "").strip()
    if serv not in SERVICIOS:
        return None, "servicio inválido"
    p = {"e": empresa_id, "s": serv, "up": usuario_id}
    for k in _CAMPOS_NUM:
        p[k] = d.get(k)
    p["acto_admin"] = (d.get("acto_admin") or "").strip() or None
    p["observacion"] = (d.get("observacion") or "").strip() or None
    p["origen"] = (d.get("origen") or "empresa").strip() or "empresa"
    # fecha_indexacion como texto 'YYYY-MM-DD' o 'YYYY-MM' (se normaliza a date en SQL con to_date si hace falta)
    fecha = (d.get("fecha_indexacion") or "").strip() or None
    p["fecha"] = _fecha(fecha)
    cid = conn.execute(text(
        "INSERT INTO costo_referencia_688(empresa_id,servicio,cargo_fijo,cargo_consumo,cma,cmo,cmi,cmict,"
        " fecha_indexacion,indice_base,acto_admin,observacion,origen,cargado_por) "
        "VALUES (:e,:s,:cargo_fijo,:cargo_consumo,:cma,:cmo,:cmi,:cmict,:fecha,:indice_base,"
        " :acto_admin,:observacion,:origen,:up) "
        "ON CONFLICT (empresa_id,servicio) DO UPDATE SET "
        " cargo_fijo=excluded.cargo_fijo, cargo_consumo=excluded.cargo_consumo, cma=excluded.cma, "
        " cmo=excluded.cmo, cmi=excluded.cmi, cmict=excluded.cmict, "
        " fecha_indexacion=excluded.fecha_indexacion, indice_base=excluded.indice_base, "
        " acto_admin=excluded.acto_admin, observacion=excluded.observacion, origen=excluded.origen, "
        " cargado_por=excluded.cargado_por, cargado_en=now() RETURNING id"), p).scalar()
    return cid, None


def eliminar(conn, empresa_id, servicio):
    conn.execute(text("DELETE FROM costo_referencia_688 WHERE empresa_id=:e AND servicio=:s"),
                 {"e": empresa_id, "s": servicio})


def completo(conn, empresa_id, servicios):
    """{servicio: bool} — True si hay fila con al menos la tarifa (CF o CC) y la fecha de indexación."""
    datos = por_servicio(conn, empresa_id)
    out = {}
    for s in servicios:
        r = datos.get(s)
        out[s] = bool(r and (r.get("cargo_fijo") is not None or r.get("cargo_consumo") is not None)
                      and r.get("fecha_indexacion"))
    return out


def _fecha(s):
    """Normaliza 'YYYY-MM-DD' o 'YYYY-MM' a 'YYYY-MM-DD' (día 1); None si no es parseable."""
    if not s:
        return None
    s = s.strip()
    partes = s.split("-")
    try:
        if len(partes) == 2:
            return f"{int(partes[0]):04d}-{int(partes[1]):02d}-01"
        if len(partes) == 3:
            return f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
    except ValueError:
        return None
    return None
