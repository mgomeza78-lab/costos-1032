# -*- coding: utf-8 -*-
"""Motor de recálculo mensual — costos económicos de referencia del mes y acumulados.

Aplica las MISMAS fórmulas validadas del estudio (núcleo `componentes_cmx`) pero con los
**drivers reales del mes** (suscriptores N, consumo corregido por pérdidas CCP y numeradores
de costo del balance clasificado), para **seguimiento/control** y para **acumular la línea
base** del recálculo anual (art. 2.1.2.1.1.9). No re-fija la tarifa cobrada: esa es el costo
del estudio indexado por el gatillo del 3 % (`operacion_service`). Aquí se compara el costo
de referencia del mes contra el cobrado para medir la **suficiencia**.

Fórmulas (pesos del año base; el cobrado ya viene indexado):
  CMA   = CACe × (1+kct) / N        × Fa_cma     (art. 2.1.2.1.3.2.1; mensual: /N, no /(N×12))
  CMO   = (COCe+CE+CIQ+COIR) × (1+kct) / CCP × Fa_cmo    (art. 2.1.2.1.3.4.1)
  CMICT = (ICTA+ITO+TA) × (1+kct) / denom × Fa_cmict     (art. 2.1.2.1.3.6.1;
          denom = CCP en acueducto, AF en alcantarillado)
  CMI   = estructural (BCR₀, anual); se reporta el valor base (indexado aparte).

CCP del mes (art. 2.1.2.1.3.3): CCP = AF + pérdidas reconocidas, con las pérdidas limitadas
al estándar IPUF* (m³/suscriptor·mes). Si las pérdidas reales ≤ estándar, se reconoce toda la
producción (CCP = AP); si las superan, se reconoce solo hasta el estándar (castigo por pérdidas).
"""
from sqlalchemy import text

CONCEPTOS = ("CACe", "COCe", "CE", "CIQ", "COIR", "ICTA", "ITO", "TA")
PERIODOS = [(2026, m) for m in (7, 8, 9, 10, 11, 12)]   # período de inicio (6 meses)
MESES_PERIODO = 12   # los numeradores base son anuales; el prorrateo mensual es /12


def base_params(conn, empresa_id):
    """base_calculo -> {servicio: {clave: valor}}."""
    rows = conn.execute(text(
        "SELECT servicio, clave, valor FROM base_calculo WHERE empresa_id=:e"),
        {"e": empresa_id}).mappings().all()
    b = {}
    for r in rows:
        b.setdefault(r["servicio"], {})[r["clave"]] = r["valor"]
    return b


def ipuf_estrella(conn, empresa_id):
    """IPUF* del segmento de la empresa (m³/suscriptor·mes)."""
    v = conn.execute(text(
        "SELECT s.ipuf_estrella FROM empresa e JOIN segmento s ON s.id=e.segmento_id "
        "WHERE e.id=:e"), {"e": empresa_id}).scalar()
    return float(v) if v is not None else 6.0


def _drivers_mes(conn, empresa_id):
    """Por (servicio, anio, mes): N (suscriptores), AF (m³ facturados), AP (m³ producidos)."""
    com = conn.execute(text(
        "SELECT servicio, anio, mes, COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3),0) af "
        "FROM carga_mensual_detalle WHERE empresa_id=:e GROUP BY servicio, anio, mes"),
        {"e": empresa_id}).mappings().all()
    mm = conn.execute(text(
        "SELECT servicio, anio, mes, COALESCE(SUM(m3_producido),0) ap, "
        "       COALESCE(SUM(m3_bloque_entregado),0) ent, COALESCE(SUM(m3_bloque_recibido),0) rec "
        "FROM macromedicion WHERE empresa_id=:e GROUP BY servicio, anio, mes"),
        {"e": empresa_id}).mappings().all()
    d = {}
    for r in com:
        d[(r["servicio"], r["anio"], r["mes"])] = {"n": float(r["n"]), "af": float(r["af"]),
                                                   "ap": 0.0, "ent": 0.0, "rec": 0.0}
    for r in mm:
        k = (r["servicio"], r["anio"], r["mes"])
        d.setdefault(k, {"n": 0.0, "af": 0.0, "ap": 0.0, "ent": 0.0, "rec": 0.0})
        d[k]["ap"] = float(r["ap"]); d[k]["ent"] = float(r["ent"]); d[k]["rec"] = float(r["rec"])
    return d


def ccp_mes(af, ap, n, ipuf):
    """Consumo corregido por pérdidas del mes (art. 2.1.2.1.3.3) con tope IPUF*.
    Pérdidas reconocidas = min(pérdidas reales, estándar IPUF*·N). Si no hay AP (p. ej.
    alcantarillado sin medición de producción), CCP = AF (sin corrección)."""
    if not ap or ap <= 0:
        return af, 0.0, 0.0
    perdidas_reales = max(ap - af, 0.0)
    estandar = ipuf * n          # m³ del mes (IPUF* es m³/susc·mes)
    reconocidas = min(perdidas_reales, estandar)
    return af + reconocidas, perdidas_reales, reconocidas


def _num_mes(conn, empresa_id):
    """numerador_mensual -> {(servicio,anio,mes): {concepto: valor}} (del balance clasificado)."""
    # SUM sobre cod_dane: el balance puede venir conjunto ('') o repartido por APS; el total
    # del mes es la suma. Con balance conjunto (lo normal) hay una sola fila por clave.
    rows = conn.execute(text(
        "SELECT servicio, anio, mes, concepto, SUM(valor) AS valor FROM numerador_mensual "
        "WHERE empresa_id=:e GROUP BY servicio, anio, mes, concepto"),
        {"e": empresa_id}).mappings().all()
    d = {}
    for r in rows:
        d.setdefault((r["servicio"], r["anio"], r["mes"]), {})[r["concepto"]] = float(r["valor"] or 0.0)
    return d


def _numeradores(base_s, num_mes_s):
    """Numeradores del mes: del balance si están, si no prorrateo del base anual (/12)."""
    if num_mes_s:
        vals = {c: num_mes_s.get(c, 0.0) for c in CONCEPTOS}
        return vals, "balance"
    vals = {c: (base_s.get(c, 0.0) or 0.0) / MESES_PERIODO for c in CONCEPTOS}
    return vals, "prorrateo_base"


def _costos(num, kct, fa_cma, fa_cmo, fa_cmict, n, ccp, denom):
    """Aplica las fórmulas del núcleo a los numeradores y drivers dados."""
    cma = (num["CACe"] * (1 + kct) / n * fa_cma) if n else None
    cot = (num["COCe"] + num["CE"] + num["CIQ"] + num["COIR"]) * (1 + kct)
    cmo = (cot / ccp * fa_cmo) if ccp else None
    cict = (num["ICTA"] + num["ITO"] + num["TA"]) * (1 + kct)
    cmict = (cict / denom * fa_cmict) if denom else None
    return cma, cmo, cmict


def recalcular(conn, empresa_id):
    """Recalcula el costo de referencia del mes y acumulado por servicio, y lo guarda."""
    base = base_params(conn, empresa_id)
    if not base:
        return 0
    ipuf = ipuf_estrella(conn, empresa_id)
    drivers = _drivers_mes(conn, empresa_id)
    nums = _num_mes(conn, empresa_id)
    # tarifa cobrada (indexada) para la brecha de suficiencia
    cobr = {}
    for r in conn.execute(text(
        "SELECT servicio, anio, mes, cargo_fijo, cargo_consumo FROM tarifa_vigente WHERE empresa_id=:e"),
        {"e": empresa_id}).mappings().all():
        cobr[(r["servicio"], r["anio"], r["mes"])] = (r["cargo_fijo"], r["cargo_consumo"])

    filas = 0
    for servicio, bs in base.items():
        kct = bs.get("kct", 0.0) or 0.0
        fa_cma = bs.get("Fa_cma", 1.0) or 1.0
        fa_cmo = bs.get("Fa_cmo", 1.0) or 1.0
        fa_cmict = bs.get("Fa_cmict", 1.0) or 1.0
        cmi_base = bs.get("CMI_base", 0.0) or 0.0
        ccp_base = bs.get("CCP") or 0.0
        af_base = bs.get("AF") or 0.0
        denom_cmict_base = bs.get("denom_cmict") or ccp_base
        es_ac = servicio.lower().startswith("acu")

        def _denom_cmict(ccp_v, af_v):
            # El denominador del CMICT del estudio (art. 2.1.2.1.3.6; CCP en acueducto, AF en
            # alcantarillado) se escala por el consumo del período, de modo que a volumen
            # proporcional reproduce el costo del estudio y a volumen distinto lo sigue.
            if es_ac:
                return denom_cmict_base * (ccp_v / ccp_base) if ccp_base else ccp_v
            return denom_cmict_base * (af_v / af_base) if af_base else af_v
        # acumuladores YTD
        ac = {c: 0.0 for c in CONCEPTOS}
        n_ac = ccp_ac = af_ac = 0.0
        # recorrer los meses del período con datos, en orden
        meses = sorted({(a, m) for (s, a, m) in drivers if s == servicio}
                       | {(a, m) for (s, a, m) in nums if s == servicio})
        for (a, m) in meses:
            dv = drivers.get((servicio, a, m), {"n": 0.0, "af": 0.0, "ap": 0.0})
            n_mes, af_mes, ap_mes = dv["n"], dv["af"], dv["ap"]
            ccp_m, perd_real, perd_rec = ccp_mes(af_mes, ap_mes, n_mes, ipuf)
            ianc = (perd_real / ap_mes * 100.0) if ap_mes else None
            num, origen = _numeradores(bs, nums.get((servicio, a, m)))
            denom_m = _denom_cmict(ccp_m, af_mes)        # CMICT: CCP (ac) / AF (al), escalado
            cma_m, cmo_m, cmict_m = _costos(num, kct, fa_cma, fa_cmo, fa_cmict,
                                            n_mes, ccp_m, denom_m)
            cmi_m = cmi_base                              # estructural (BCR₀ anual)
            # acumular
            for c in CONCEPTOS:
                ac[c] += num[c]
            n_ac += n_mes; ccp_ac += ccp_m; af_ac += af_mes
            denom_a = _denom_cmict(ccp_ac, af_ac)
            cma_a, cmo_a, cmict_a = _costos(ac, kct, fa_cma, fa_cmo, fa_cmict,
                                            n_ac, ccp_ac, denom_a)
            cmi_a = cmi_base
            # suficiencia vs cobrado (indexado)
            cf, cc = cobr.get((servicio, a, m), (None, None))
            ref_cf = cma_m
            ref_cc = (cmo_m or 0.0) + cmi_m + (cmict_m or 0.0)
            brecha_cf = (cf - ref_cf) if (cf is not None and ref_cf is not None) else None
            brecha_cc = (cc - ref_cc) if (cc is not None) else None
            conn.execute(text(
                "INSERT INTO costo_referencia_mensual(empresa_id,anio,mes,servicio,"
                " n_mes,af_mes,ap_mes,perdidas_mes,ianc,ccp_mes,"
                " cma_mes,cmo_mes,cmi_mes,cmict_mes,ccp_acum,cma_acum,cmo_acum,cmi_acum,cmict_acum,"
                " cobrado_cf,cobrado_cc,ref_cf,ref_cc,brecha_cf,brecha_cc,origen_numerador) "
                "VALUES (:e,:a,:m,:s,:n,:af,:ap,:pm,:ia,:ccp,"
                " :cma,:cmo,:cmi,:cmict,:ccpa,:cmaa,:cmoa,:cmia,:cmicta,"
                " :ccf,:ccc,:rcf,:rcc,:bcf,:bcc,:org) "
                "ON CONFLICT (empresa_id,anio,mes,servicio) DO UPDATE SET "
                " n_mes=excluded.n_mes, af_mes=excluded.af_mes, ap_mes=excluded.ap_mes, "
                " perdidas_mes=excluded.perdidas_mes, ianc=excluded.ianc, ccp_mes=excluded.ccp_mes, "
                " cma_mes=excluded.cma_mes, cmo_mes=excluded.cmo_mes, cmi_mes=excluded.cmi_mes, "
                " cmict_mes=excluded.cmict_mes, ccp_acum=excluded.ccp_acum, cma_acum=excluded.cma_acum, "
                " cmo_acum=excluded.cmo_acum, cmi_acum=excluded.cmi_acum, cmict_acum=excluded.cmict_acum, "
                " cobrado_cf=excluded.cobrado_cf, cobrado_cc=excluded.cobrado_cc, "
                " ref_cf=excluded.ref_cf, ref_cc=excluded.ref_cc, brecha_cf=excluded.brecha_cf, "
                " brecha_cc=excluded.brecha_cc, origen_numerador=excluded.origen_numerador, "
                " calculado_en=now()"),
                {"e": empresa_id, "a": a, "m": m, "s": servicio, "n": n_mes, "af": af_mes,
                 "ap": ap_mes, "pm": perd_real, "ia": ianc, "ccp": ccp_m,
                 "cma": cma_m, "cmo": cmo_m, "cmi": cmi_m, "cmict": cmict_m,
                 "ccpa": ccp_ac, "cmaa": cma_a, "cmoa": cmo_a, "cmia": cmi_a, "cmicta": cmict_a,
                 "ccf": cf, "ccc": cc, "rcf": ref_cf, "rcc": ref_cc,
                 "bcf": brecha_cf, "bcc": brecha_cc, "org": origen})
            filas += 1
    return filas


def split_servicio(conn, empresa_id):
    """Participación de acueducto por concepto (ac/(ac+al)) según los numeradores base,
    para repartir el balance mensual (que viene por el total de la empresa) entre servicios."""
    base = base_params(conn, empresa_id)
    ac = base.get("acueducto", {})
    al = base.get("alcantarillado", {})
    split = {}
    for c in CONCEPTOS:
        a = ac.get(c, 0.0) or 0.0
        b = al.get(c, 0.0) or 0.0
        split[c] = (a / (a + b)) if (a + b) else 1.0
    return split


def tablero(conn, empresa_id):
    """Resultados del recálculo por servicio, ordenados por mes, para la UI."""
    rows = conn.execute(text(
        "SELECT servicio, anio, mes, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, "
        " cma_mes, cmo_mes, cmi_mes, cmict_mes, cma_acum, cmo_acum, cmi_acum, cmict_acum, "
        " cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador "
        "FROM costo_referencia_mensual WHERE empresa_id=:e ORDER BY servicio, anio, mes"),
        {"e": empresa_id}).mappings().all()
    por = {}
    for r in rows:
        por.setdefault(r["servicio"], []).append(dict(r))
    return por
