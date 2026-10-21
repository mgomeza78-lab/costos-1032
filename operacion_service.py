# -*- coding: utf-8 -*-
"""Motor de operación mensual — indexación por gatillo del 3 % y factura por estrato.

Res. CRA 1032 (art. 2.1.2.1.5.3) y art. 125 de la Ley 142 de 1994: los cargos se
actualizan cuando la variación acumulada del índice alcanza el 3 % desde la última
actualización. La 1032 usa DOS canastas: **IPCs** para CMA/CMO/CMICT e **IPC** para CMI
(cada una con su propio gatillo). La tarifa vigente = cargo fijo (CMA) + cargo por consumo
(CMO+CMI+CMICT), indexados por su canasta.

La **factura teórica por estrato** se deriva de los suscriptores y consumos (cargue
comercial del SUI) y la tarifa vigente, aplicando los factores de subsidio/contribución.
"""
from sqlalchemy import text

GATILLO = 0.03                       # 3 % (art. 125 Ley 142)
PERIODOS = [(2026, m) for m in (7, 8, 9, 10, 11, 12)]   # período de inicio
MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
MES_BASE = (2026, 7)
CLASES = {1: "Estrato 1", 2: "Estrato 2", 3: "Estrato 3", 4: "Estrato 4",
          5: "Estrato 5", 6: "Estrato 6", 10: "Industrial", 11: "Comercial",
          12: "Oficial", 13: "Especial"}   # códigos CLASEUSO del SUI


def componentes_base(conn, empresa_id):
    """CMA/CMO/CMI/CMICT base (período de inicio) por servicio."""
    rows = conn.execute(text(
        "SELECT servicio, componente, valor FROM resultado_componente "
        "WHERE empresa_id=:e AND componente IN ('CMA','CMO','CMI','CMICT')"),
        {"e": empresa_id}).mappings().all()
    base = {}
    for r in rows:
        base.setdefault(r["servicio"], {})[r["componente"].lower()] = r["valor"]
    return base


def serie_ipc(conn):
    """{(anio,mes): (ipc, ipcs)}; ipcs cae a ipc si no está cargado."""
    rows = conn.execute(text("SELECT anio, mes, indice, ipcs FROM indice_ipc")).mappings().all()
    s = {}
    for r in rows:
        ipc = float(r["indice"])
        ipcs = float(r["ipcs"]) if r["ipcs"] is not None else ipc
        s[(r["anio"], r["mes"])] = (ipc, ipcs)
    return s


def procesar_empresa(conn, empresa_id, gatillo=GATILLO):
    """Indexa por componente (dos canastas) y actualiza tarifa_vigente."""
    base = componentes_base(conn, empresa_id)
    ipc = serie_ipc(conn)
    b0 = ipc.get(MES_BASE)
    if not b0:
        return 0, 0
    ipc0, ipcs0 = b0
    filas = indexaciones = 0
    for servicio, c in base.items():
        cma = c.get("cma") or 0.0
        cmo = c.get("cmo") or 0.0
        cmi = c.get("cmi") or 0.0
        cmict = c.get("cmict") or 0.0
        cma0 = cma or 1.0
        ref_ipcs, ref_ipc = ipcs0, ipc0
        for (a, m) in PERIODOS:
            v = ipc.get((a, m))
            if not v:
                continue
            ipc_m, ipcs_m = v
            var_ipcs = ipcs_m / ref_ipcs - 1.0
            var_ipc = ipc_m / ref_ipc - 1.0
            ixs = var_ipcs >= gatillo          # canasta CMA/CMO/CMICT
            ixc = var_ipc >= gatillo           # canasta CMI
            if ixs:
                f = ipcs_m / ref_ipcs
                cma *= f; cmo *= f; cmict *= f
                ref_ipcs = ipcs_m
                indexaciones += 1
            if ixc:
                f2 = ipc_m / ref_ipc
                cmi *= f2
                ref_ipc = ipc_m
                indexaciones += 1
            cf = cma
            cc = cmo + cmi + cmict
            conn.execute(text(
                "INSERT INTO tarifa_vigente "
                "(empresa_id,anio,mes,servicio,cargo_fijo,cargo_consumo,factor_acumulado,"
                " variacion_acum,indexado,var_ipc,indexado_ipc) "
                "VALUES (:e,:a,:m,:s,:cf,:cc,:fa,:vs,:ixs,:vc,:ixc) "
                "ON CONFLICT (empresa_id,anio,mes,servicio) DO UPDATE SET "
                " cargo_fijo=excluded.cargo_fijo, cargo_consumo=excluded.cargo_consumo, "
                " factor_acumulado=excluded.factor_acumulado, variacion_acum=excluded.variacion_acum, "
                " indexado=excluded.indexado, var_ipc=excluded.var_ipc, "
                " indexado_ipc=excluded.indexado_ipc, calculado_en=now()"),
                {"e": empresa_id, "a": a, "m": m, "s": servicio, "cf": cf, "cc": cc,
                 "fa": cf / cma0, "vs": var_ipcs, "ixs": ixs, "vc": var_ipc, "ixc": ixc})
            filas += 1
    return filas, indexaciones


def derivar_factura(conn, empresa_id):
    """Factura teórica por clase = tarifa vigente × cantidades, con subsidios/contribuciones."""
    rows = conn.execute(text(
        "SELECT d.anio, d.mes, d.servicio, d.clase, d.suscriptores, d.m3, d.m3_subsidiable, "
        "       tv.cargo_fijo, tv.cargo_consumo, fs.factor_cargofijo, fs.factor_consumo "
        "FROM carga_mensual_detalle d "
        "JOIN tarifa_vigente tv ON tv.empresa_id=d.empresa_id AND tv.anio=d.anio "
        "     AND tv.mes=d.mes AND tv.servicio=d.servicio "
        "LEFT JOIN factor_subsidio fs ON fs.empresa_id=d.empresa_id AND fs.vigencia=d.anio "
        "     AND fs.servicio=d.servicio AND fs.clase=d.clase "
        "WHERE d.empresa_id=:e"), {"e": empresa_id}).mappings().all()
    filas = 0
    for r in rows:
        CF = r["cargo_fijo"] or 0.0
        CC = r["cargo_consumo"] or 0.0
        fcf = r["factor_cargofijo"] or 0.0
        fcc = r["factor_consumo"] or 0.0
        susc = r["suscriptores"] or 0
        m3 = r["m3"] or 0.0
        m3s = r["m3_subsidiable"] or 0.0
        cf_fact = susc * CF * (1 + fcf)
        cc_fact = CC * (m3s * (1 + fcc) + (m3 - m3s))
        sub = susc * CF * fcf + CC * m3s * fcc
        conn.execute(text(
            "INSERT INTO factura_clase(empresa_id,anio,mes,servicio,clase,suscriptores,m3,"
            " m3_subsidiable,cf_facturado,cc_facturado,subsidio_contribucion,factura_total) "
            "VALUES (:e,:a,:m,:s,:c,:su,:m3,:ms,:cf,:cc,:sb,:tot) "
            "ON CONFLICT (empresa_id,anio,mes,servicio,clase) DO UPDATE SET "
            " suscriptores=excluded.suscriptores, m3=excluded.m3, m3_subsidiable=excluded.m3_subsidiable, "
            " cf_facturado=excluded.cf_facturado, cc_facturado=excluded.cc_facturado, "
            " subsidio_contribucion=excluded.subsidio_contribucion, factura_total=excluded.factura_total, "
            " calculado_en=now()"),
            {"e": empresa_id, "a": r["anio"], "m": r["mes"], "s": r["servicio"], "c": r["clase"],
             "su": susc, "m3": m3, "ms": m3s, "cf": cf_fact, "cc": cc_fact, "sb": sub,
             "tot": cf_fact + cc_fact})
        filas += 1
    return filas


def tablero(conn, empresa_id):
    rows = conn.execute(text(
        "SELECT tv.servicio, tv.anio, tv.mes, tv.cargo_fijo, tv.cargo_consumo, "
        "       tv.factor_acumulado, tv.variacion_acum, tv.indexado, tv.var_ipc, tv.indexado_ipc, "
        "       ip.indice AS ipc, ip.ipcs, "
        "       cm.suscriptores, cm.m3_facturados "
        "FROM tarifa_vigente tv "
        "LEFT JOIN indice_ipc ip ON ip.anio=tv.anio AND ip.mes=tv.mes "
        "LEFT JOIN carga_mensual cm ON cm.empresa_id=tv.empresa_id AND cm.anio=tv.anio "
        "     AND cm.mes=tv.mes AND cm.servicio=tv.servicio "
        "WHERE tv.empresa_id=:e ORDER BY tv.servicio, tv.anio, tv.mes"),
        {"e": empresa_id}).mappings().all()
    por = {}
    for r in rows:
        por.setdefault(r["servicio"], []).append(dict(r))
    return por


def meses_con_factura(conn, empresa_id):
    rows = conn.execute(text(
        "SELECT DISTINCT anio, mes FROM factura_clase WHERE empresa_id=:e ORDER BY anio, mes"),
        {"e": empresa_id}).all()
    return [(r[0], r[1]) for r in rows]


def tablero_factura(conn, empresa_id, anio, mes):
    rows = conn.execute(text(
        "SELECT servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, "
        "       subsidio_contribucion, factura_total FROM factura_clase "
        "WHERE empresa_id=:e AND anio=:a AND mes=:m ORDER BY servicio, clase"),
        {"e": empresa_id, "a": anio, "m": mes}).mappings().all()
    por = {}
    for r in rows:
        d = por.setdefault(r["servicio"], {"filas": [], "tot_susc": 0, "tot_fact": 0.0, "tot_sub": 0.0})
        d["filas"].append(dict(r))
        d["tot_susc"] += r["suscriptores"] or 0
        d["tot_fact"] += r["factura_total"] or 0.0
        d["tot_sub"] += r["subsidio_contribucion"] or 0.0
    return por
