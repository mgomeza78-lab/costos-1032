# -*- coding: utf-8 -*-
"""Factor de ajuste del ISUF (Fap) para el CCP — Res. CRA 1032, parágrafo 3 del art. 2.1.2.1.3.3.1.

El ajuste del ISUF es OPTATIVO: ISUF_ajustado = ISUF − Fap. El Fap se escoge de una
tabla con cuatro entradas: (a) rango del IPUFreal, (b) Índice de Vulnerabilidad
Hídrica -IVH (IDEAM, subzona de captación), (c) metodología anterior aplicada
(688/825) y (d) para la 688, si se cumplió la meta del IPUF (diferencia ≤ 20 %).

El Fap es ÚNICO por prestador: el CCP de ambos servicios se construye sobre el
ISUF del acueducto (CCP_ac = (ISUF_ac − IPUF*)·N_ac·12;
CCP_al = (ISUF_ac − ICUF_ac + ICUF_al − IPUF*)·N_al·12) y el Fap ajusta ese ISUF_ac.
No existe un Fap de alcantarillado.

El sistema no pide lo que puede derivar:
  · IPUFreal de la ventana IRD1 (1-jul-2024 a 30-jun-2025, numeral 6.2.2.1.1., Libro 6):
    se calcula de lo cargado = Σ(AP − AF)/ΣN del acueducto.
  · Metodología anterior: del punto de partida (bcr_param.fecha_inicio_688).
  · Cumplimiento de la meta de la 688: lo valida el sistema (≤ 20 %) con la meta del
    IPUF de los años tarifarios 9 y 10 que ingresa el usuario; gobierna el año 10.
"""
import datetime as _dt
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

# Ventana del IPUFreal del período de inicio (indicador IRD1): 1-jul-2024 a 30-jun-2025.
VENTANA_IRD1 = [(2024, m) for m in range(7, 13)] + [(2025, m) for m in range(1, 7)]


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


# ---------------------------------------------------------------------------
#  Derivación de insumos (no se digitan): metodología, IPUFreal, años 688.
# ---------------------------------------------------------------------------
def _as_date(v):
    if v is None or isinstance(v, _dt.date):
        return v
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def _metodologia_y_fecha(conn, empresa_id):
    """Metodología anterior y fecha de inicio de la 688.

    Metodología: la EXPLÍCITA de la empresa (selector de «crear/editar empresa»,
    empresa.metodologia_anterior). Si no se eligió, se infiere: 688 si hay fecha de inicio
    de la 688 (en la empresa o en el BCR₀), si no 825. La fecha se usa además para mapear
    los años tarifarios 9 y 10 de la 688 (se prefiere la del BCR₀, por servicio)."""
    r = conn.execute(text(
        "SELECT metodologia_anterior, fecha_inicio_688 FROM empresa WHERE id=:e"),
        {"e": empresa_id}).mappings().first()
    met_exp = (r["metodologia_anterior"] if r else None)
    fe = _as_date(r["fecha_inicio_688"]) if r else None
    fb = _as_date(conn.execute(text(
        "SELECT fecha_inicio_688 FROM bcr_param WHERE empresa_id=:e AND servicio='acueducto'"),
        {"e": empresa_id}).scalar())
    fecha = fb or fe
    metod = met_exp if met_exp in ("688", "825") else ("688" if fecha else "825")
    return metod, fecha


def _k688(fecha_inicio, anio, mes):
    """Año tarifario de la 688 (1, 2, …) al que pertenece un mes calendario; None si no aplica."""
    if not fecha_inicio:
        return None
    ms = (anio - fecha_inicio.year) * 12 + (mes - fecha_inicio.month)
    return (ms // 12 + 1) if ms >= 0 else None


def _series_acueducto(conn, empresa_id):
    """Por (anio, mes) del acueducto: AP (macromedición), AF y N (comercial, conjunto)."""
    ap = {(r["anio"], r["mes"]): float(r["ap"]) for r in conn.execute(text(
        "SELECT anio, mes, COALESCE(SUM(m3_producido),0) ap FROM macromedicion "
        "WHERE empresa_id=:e AND LOWER(servicio) LIKE 'acu%' GROUP BY anio, mes"),
        {"e": empresa_id}).mappings().all()}
    out = {}
    for r in conn.execute(text(
            "SELECT anio, mes, COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3_facturados),0) af "
            "FROM carga_mensual WHERE empresa_id=:e AND LOWER(servicio) LIKE 'acu%' AND cod_dane='' "
            "GROUP BY anio, mes"), {"e": empresa_id}).mappings().all():
        k = (r["anio"], r["mes"])
        out[k] = {"n": float(r["n"]), "af": float(r["af"]), "ap": ap.get(k, 0.0)}
    return out


def _ipuf(series, meses):
    """IPUF real = Σ(AP−AF)/ΣN sobre los meses con dato completo (AP, AF, N > 0)."""
    sp = su = 0.0
    nm = 0
    for k in meses:
        d = series.get(k)
        if d and d["ap"] > 0 and d["af"] > 0 and d["n"] > 0:
            sp += d["ap"] - d["af"]
            su += d["n"]
            nm += 1
    if su <= 0:
        return None, 0.0, 0.0, 0
    return sp / su, sp, su, nm


def _isuf(series, meses):
    """ISUF = ΣAP/ΣN sobre los meses con AP y N > 0 (agua suministrada por suscriptor facturado)."""
    sa = su = 0.0
    for k in meses:
        d = series.get(k)
        if d and d["ap"] > 0 and d["n"] > 0:
            sa += d["ap"]
            su += d["n"]
    return (sa / su) if su > 0 else None


def _computar(conn, empresa_id, inputs):
    """Calcula metodología, IPUFreal (ventana y años 688 9/10), cumplimiento y Fap a partir
    de los insumos del usuario (aplica, ivh, ipuf_meta_a9/a10) y de lo cargado."""
    metod, fecha = _metodologia_y_fecha(conn, empresa_id)
    series = _series_acueducto(conn, empresa_id)
    ir_v, perd_v, usu_v, nm_v = _ipuf(series, VENTANA_IRD1)
    isuf_v = _isuf(series, VENTANA_IRD1)
    # Reales por año tarifario de la 688 (todos los meses cargados que mapean a 9 / 10).
    m9 = [k for k in series if _k688(fecha, k[0], k[1]) == 9]
    m10 = [k for k in series if _k688(fecha, k[0], k[1]) == 10]
    ir9 = _ipuf(series, m9)[0] if fecha else None
    ir10 = _ipuf(series, m10)[0] if fecha else None

    meta9 = inputs.get("ipuf_meta_a9")
    meta10 = inputs.get("ipuf_meta_a10")
    ivh = inputs.get("ivh") or None
    aplica = inputs.get("aplica", True)

    es688 = (metod == "688")
    cum9 = cumplimiento_meta(meta9, ir9) if es688 else None
    cum10 = cumplimiento_meta(meta10, ir10) if es688 else None
    # Cumplimiento que GOBIERNA el Fap: año 10 (cierra la senda 688 y es el más cercano al
    # período de inicio); si no hay par meta+real del 10, se usa el 9; en última instancia,
    # la meta disponible contra el IPUFreal de la ventana.
    meta_gob = cumplio = None
    if es688:
        if meta10 is not None and ir10 is not None:
            meta_gob, real_gob = meta10, ir10
        elif meta9 is not None and ir9 is not None:
            meta_gob, real_gob = meta9, ir9
        else:
            meta_gob = meta10 if meta10 is not None else meta9
            real_gob = ir_v
        cumplio = cumplimiento_meta(meta_gob, real_gob) if meta_gob is not None else None

    fap, nota, rango = fap_resuelto({"aplica": aplica, "ipuf_real": ir_v, "ivh": ivh,
                                     "metodologia": metod, "cumplio_meta": cumplio})
    isuf_aj = (isuf_v - fap) if (aplica and isuf_v is not None and fap is not None) else None

    falta = []
    if ir_v is None:
        falta.append("agua producida y/o facturación del acueducto en la ventana IRD1 (jul-2024 a jun-2025)")
    if es688 and not fecha:
        falta.append("fecha de inicio de la 688 (punto de partida) para separar los años tarifarios 9 y 10")
    if ivh is None:
        falta.append("IVH del IDEAM (ENA) de la subzona de captación")
    if es688 and meta_gob is None:
        falta.append("meta del IPUF de la 688 (año tarifario 9 y/o 10)")

    return {
        "metodologia": metod, "fecha_inicio_688": fecha,
        "ipuf_real_ventana": ir_v, "perdidas_ventana": perd_v, "usuarios_ventana": usu_v,
        "meses_ventana": nm_v, "isuf_ventana": isuf_v, "isuf_ajustado": isuf_aj,
        "ipuf_real_a9": ir9, "ipuf_real_a10": ir10,
        "meta_a9": meta9, "meta_a10": meta10,
        "umbral_a9": (meta9 * 1.20 if meta9 is not None else None),
        "umbral_a10": (meta10 * 1.20 if meta10 is not None else None),
        "cumple_a9": cum9, "cumple_a10": cum10,
        "meta_gobierna": meta_gob, "cumplio": cumplio,
        "aplica": aplica, "ivh": ivh,
        "fap": fap, "nota": nota, "rango": rango, "falta": falta,
    }


def get(conn, empresa_id, servicio=None):
    """Fila única del Fap de la empresa (el parámetro servicio se ignora: el Fap es único)."""
    return conn.execute(text("SELECT * FROM ccp_fap WHERE empresa_id=:e"),
                        {"e": empresa_id}).mappings().first()


def vista(conn, empresa_id):
    """Modelo de vista del Fap para la plantilla: insumos guardados + cálculo en vivo."""
    row = get(conn, empresa_id)
    inputs = {"aplica": (bool(row["aplica"]) if row else True),
              "ivh": (row["ivh"] if row else None),
              "ipuf_meta_a9": (row["ipuf_meta_a9"] if row else None),
              "ipuf_meta_a10": (row["ipuf_meta_a10"] if row else None)}
    v = _computar(conn, empresa_id, inputs)
    v["observacion"] = (row["observacion"] if row else None)
    v["guardado"] = bool(row)
    return v


def set_fap(conn, empresa_id, d):
    """Calcula (metodología, IPUFreal, cumplimiento, Fap) y guarda la fila única (upsert)."""
    v = _computar(conn, empresa_id, d)
    conn.execute(text(
        "INSERT INTO ccp_fap(empresa_id,servicio,aplica,ipuf_real,ipuf_planeado,ipuf_meta_a9,"
        " ipuf_meta_a10,ivh,metodologia,cumplio_meta,periodo,fap,observacion) "
        "VALUES (:e,'acueducto',:ap,:ir,:ig,:m9,:m10,:iv,:me,:cm,:pe,:fa,:ob) "
        "ON CONFLICT (empresa_id) DO UPDATE SET aplica=excluded.aplica, ipuf_real=excluded.ipuf_real, "
        " ipuf_planeado=excluded.ipuf_planeado, ipuf_meta_a9=excluded.ipuf_meta_a9, "
        " ipuf_meta_a10=excluded.ipuf_meta_a10, ivh=excluded.ivh, metodologia=excluded.metodologia, "
        " cumplio_meta=excluded.cumplio_meta, periodo=excluded.periodo, fap=excluded.fap, "
        " observacion=excluded.observacion, actualizado_en=now()"),
        {"e": empresa_id, "ap": bool(d.get("aplica", True)), "ir": v["ipuf_real_ventana"],
         "ig": v["meta_gobierna"], "m9": d.get("ipuf_meta_a9"), "m10": d.get("ipuf_meta_a10"),
         "iv": (d.get("ivh") or None), "me": v["metodologia"], "cm": v["cumplio"],
         "pe": (d.get("periodo") or "inicio"), "fa": v["fap"],
         "ob": (d.get("observacion") or "").strip() or None})
    return v["fap"], v["nota"]
