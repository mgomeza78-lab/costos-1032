# -*- coding: utf-8 -*-
"""Factor de ajuste del ISUF (Fap) para el CCP (Res. CRA 1032, parágrafo 3 del artículo del CCP).

El ajuste del ISUF es OPTATIVO: ISUF_ajustado = ISUF − Fap. El Fap se escoge de una
tabla con cuatro entradas: (a) rango del IPUFreal, (b) Índice de Vulnerabilidad
Hídrica -IVH (IDEAM, subzona de captación), (c) metodología anterior aplicada
(688/825) y (d) para la 688, si se cumplió la meta del IPUF (diferencia ≤ 20 %).
Para el período de inicio, el IPUFreal es el del 1-jul-2024 a 30-jun-2025 (indicador IRD1).
"""
from sqlalchemy import text

IVH_OPC = {"muy_baja": "Muy baja", "baja": "Baja", "media": "Media", "alta": "Alta", "muy_alta": "Muy alta"}
MET_OPC = {"688": "Res. CRA 688 de 2014", "825": "Res. CRA 825 de 2017"}
IVH_ALTO = {"alta", "muy_alta"}

# Tabla de factores de ajuste del ISUF (Fap) por rango de IPUFreal, grupo de IVH y
# metodología/cumplimiento. Clave de columna: '688_no', '688_si', '825'.
FAP = {
    0: {"bajo": {"688_no": 0.47, "688_si": 0.78, "825": 0.78},
        "alto": {"688_no": 0.31, "688_si": 0.62, "825": 0.62}},   # 6 < IPUFreal ≤ 8
    1: {"bajo": {"688_no": 0.49, "688_si": 0.81, "825": 0.81},
        "alto": {"688_no": 0.33, "688_si": 0.65, "825": 0.65}},   # 8 < IPUFreal ≤ 11,5
    2: {"bajo": {"688_no": 1.20, "688_si": 2.00, "825": 2.00},
        "alto": {"688_no": 0.80, "688_si": 1.60, "825": 1.60}},   # 11,5 < IPUFreal ≤ 15
    3: {"bajo": {"688_no": 2.40, "688_si": 4.00, "825": 4.00},
        "alto": {"688_no": 1.60, "688_si": 3.20, "825": 3.20}},   # IPUFreal > 15
}
RANGO_ET = {0: "6 < IPUFreal ≤ 8", 1: "8 < IPUFreal ≤ 11,5", 2: "11,5 < IPUFreal ≤ 15", 3: "IPUFreal > 15"}


def _rango(x):
    if x <= 8:
        return 0
    if x <= 11.5:
        return 1
    if x <= 15:
        return 2
    return 3


def cumplimiento_meta(ipuf_planeado, ipuf_real):
    """Res. 688: se cumple la meta cuando la diferencia IPUF real−planeado ≤ 20 % del planeado."""
    if ipuf_planeado in (None, 0) or ipuf_real is None:
        return None
    return (float(ipuf_real) - float(ipuf_planeado)) <= 0.20 * float(ipuf_planeado)


def fap_resuelto(d):
    """Devuelve (fap, nota, rango_etiqueta) según las cuatro entradas. 0 si no aplica."""
    if not d.get("aplica", True):
        return 0.0, "Ajuste del ISUF no aplicado (optativo)", None
    ipuf = d.get("ipuf_real")
    if ipuf is None:
        return None, "Falta el IPUFreal", None
    ipuf = float(ipuf)
    if ipuf <= 6:
        return 0.0, "IPUFreal ≤ 6: no aplica ajuste (ya en el estándar)", None
    ri = _rango(ipuf)
    grupo = "alto" if d.get("ivh") in IVH_ALTO else ("bajo" if d.get("ivh") else None)
    if grupo is None:
        return None, "Falta el IVH", RANGO_ET[ri]
    met = d.get("metodologia")
    if met == "825":
        col = "825"
    elif met == "688":
        cm = d.get("cumplio_meta")
        if cm is None:
            return None, "Falta el cumplimiento de la meta (688)", RANGO_ET[ri]
        col = "688_si" if cm else "688_no"
    else:
        return None, "Falta la metodología anterior (688/825)", RANGO_ET[ri]
    return FAP[ri][grupo][col], "Fap resuelto de la tabla", RANGO_ET[ri]


def get(conn, empresa_id, servicio="acueducto"):
    return conn.execute(text("SELECT * FROM ccp_fap WHERE empresa_id=:e AND servicio=:s"),
                        {"e": empresa_id, "s": servicio}).mappings().first()


def set_fap(conn, empresa_id, servicio, d):
    """Resuelve el cumplimiento (si 688), calcula el Fap y guarda (upsert)."""
    if servicio not in ("acueducto", "alcantarillado"):
        return None, "servicio inválido"
    met = (d.get("metodologia") or "").strip() or None
    cm = d.get("cumplio_meta")
    if met == "688" and cm is None:
        cm = cumplimiento_meta(d.get("ipuf_planeado"), d.get("ipuf_real"))
    if met != "688":
        cm = None
    fap, nota, _ = fap_resuelto({"aplica": d.get("aplica", True), "ipuf_real": d.get("ipuf_real"),
                                 "ivh": (d.get("ivh") or None), "metodologia": met, "cumplio_meta": cm})
    conn.execute(text(
        "INSERT INTO ccp_fap(empresa_id,servicio,aplica,ipuf_real,ipuf_planeado,ivh,metodologia,"
        " cumplio_meta,periodo,fap,observacion) "
        "VALUES (:e,:s,:ap,:ir,:ip,:iv,:me,:cm,:pe,:fa,:ob) "
        "ON CONFLICT (empresa_id,servicio) DO UPDATE SET aplica=excluded.aplica, "
        " ipuf_real=excluded.ipuf_real, ipuf_planeado=excluded.ipuf_planeado, ivh=excluded.ivh, "
        " metodologia=excluded.metodologia, cumplio_meta=excluded.cumplio_meta, periodo=excluded.periodo, "
        " fap=excluded.fap, observacion=excluded.observacion, actualizado_en=now()"),
        {"e": empresa_id, "s": servicio, "ap": bool(d.get("aplica", True)), "ir": d.get("ipuf_real"),
         "ip": d.get("ipuf_planeado"), "iv": (d.get("ivh") or None), "me": met, "cm": cm,
         "pe": (d.get("periodo") or "inicio"), "fa": fap, "ob": (d.get("observacion") or "").strip() or None})
    return fap, nota
