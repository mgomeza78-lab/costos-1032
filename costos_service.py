# -*- coding: utf-8 -*-
"""Costos particulares de la Res. CRA 1032 — captura por año y servicio.

Insumo de la pestaña «Costos particulares» del menú de carga de información. Son
costos que la metodología reconoce de forma particular para la persona prestadora
(p. ej. tasas ambientales, contratos de suministro, costos de operación específicos).
Se etiquetan con el año al que corresponden, de modo que el sistema los asocia al
año tarifario respectivo. No se inventan valores: los aporta la empresa.
"""
from sqlalchemy import text

SERVICIOS = {"acueducto": "Acueducto", "alcantarillado": "Alcantarillado", "general": "General"}
# Costos operativos particulares (COP, art. 2.1.2.1.3.4.5) — categorías alineadas a los modelos.
CATEGORIAS = ["Energía (CE)", "Insumos químicos (CIQ)", "Tratamiento aguas residuales",
              "Contrato de suministro / interconexión", "COIR (inversiones ambientales)", "Otro"]


def lista(conn, empresa_id, anio=None):
    sql = ("SELECT id, anio, servicio, categoria, concepto, valor, unidad, cantidad, precio_unitario, "
           "       cuenta_contable, valor_contable, origen, soporte, observacion "
           "FROM costo_particular WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    sql += " ORDER BY anio DESC, servicio, categoria, concepto"
    return conn.execute(text(sql), p).mappings().all()


def anios(conn, empresa_id):
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT anio FROM costo_particular WHERE empresa_id=:e ORDER BY anio DESC"),
        {"e": empresa_id}).all()]


def guardar(conn, empresa_id, d, usuario_id):
    serv = (d.get("servicio") or "acueducto").strip()
    if serv not in SERVICIOS:
        return None, "servicio inválido"
    concepto = (d.get("concepto") or "").strip()
    if not concepto:
        return None, "el concepto es obligatorio"
    try:
        anio = int(d.get("anio"))
    except (TypeError, ValueError):
        return None, "año inválido"
    cid = conn.execute(text(
        "INSERT INTO costo_particular(empresa_id,anio,servicio,categoria,concepto,valor,unidad,"
        " cantidad,precio_unitario,cuenta_contable,valor_contable,soporte,origen,observacion,cargado_por) "
        "VALUES (:e,:a,:s,:cat,:c,:v,:u,:qty,:pu,:cc,:vc,:sp,:og,:ob,:up) "
        "ON CONFLICT (empresa_id,anio,servicio,concepto) DO UPDATE SET "
        " categoria=excluded.categoria, valor=excluded.valor, unidad=excluded.unidad, "
        " cantidad=excluded.cantidad, precio_unitario=excluded.precio_unitario, "
        " cuenta_contable=excluded.cuenta_contable, valor_contable=excluded.valor_contable, "
        " soporte=excluded.soporte, origen=excluded.origen, observacion=excluded.observacion, "
        " cargado_por=excluded.cargado_por, cargado_en=now() RETURNING id"),
        {"e": empresa_id, "a": anio, "s": serv, "cat": (d.get("categoria") or "").strip() or None,
         "c": concepto, "v": d.get("valor"), "u": (d.get("unidad") or "").strip() or None,
         "qty": d.get("cantidad"), "pu": d.get("precio_unitario"),
         "cc": (d.get("cuenta_contable") or "").strip() or None, "vc": d.get("valor_contable"),
         "sp": (d.get("soporte") or "").strip() or None, "og": (d.get("origen") or "empresa").strip(),
         "ob": (d.get("observacion") or "").strip() or None, "up": usuario_id}).scalar()
    return cid, None


def eliminar(conn, empresa_id, cid):
    conn.execute(text("DELETE FROM costo_particular WHERE empresa_id=:e AND id=:i"),
                 {"e": empresa_id, "i": cid})


def resumen(conn, empresa_id):
    """Totales por año y servicio (para la pestaña de carga)."""
    rows = conn.execute(text(
        "SELECT anio, servicio, count(*) AS n, sum(valor) AS total, sum(valor_contable) AS total_contable "
        "FROM costo_particular WHERE empresa_id=:e GROUP BY anio, servicio ORDER BY anio DESC, servicio"),
        {"e": empresa_id}).mappings().all()
    return [dict(r) for r in rows]


def ajuste_coc(conn, empresa_id, anio=None):
    """Resta al COC por costos particulares ya registrados en contabilidad (evita el doble conteo
    frente al costo operativo comparable, art. 2.1.2.1.3.4.4/.5). Devuelve, por servicio y año, la
    suma del valor contable registrado que debe descontarse del COC."""
    sql = ("SELECT servicio, anio, coalesce(sum(valor_contable),0) AS resta_coc, "
           "       count(*) FILTER (WHERE valor_contable IS NOT NULL) AS n "
           "FROM costo_particular WHERE empresa_id=:e AND valor_contable IS NOT NULL")
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    sql += " GROUP BY servicio, anio ORDER BY anio DESC, servicio"
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]
