# -*- coding: utf-8 -*-
"""Vista del CCP (Consumo Corregido por Pérdidas) — Res. CRA 1032, art. 2.1.2.1.3.3 y ss.

Reúne, de forma trazable, TODO lo que entra al CCP del período de inicio:
  · datos base por servicio (Σ suscriptores-mes N, Σ m³ facturados AF, Σ m³ producidos AP);
  · indicadores por unidad de facturación: ICUF, IPUF (real), ISUF = ICUF + IPUF;
  · IPUF real vs IPUF aplicado en el CCP (tope IPUF*, art. 2.1.2.1.3.5.2 par. 1);
  · senda de gradualidad del IPUF* por año tarifario (art. 2.1.2.1.2.3);
  · Fap (ajuste optativo del ISUF, ccp_service) e ISUF ajustado;
  · CCP resultante = AF + pérdidas reconocidas.

No inventa datos: lo que no esté cargado se reporta como faltante.
"""
from sqlalchemy import text
import recalculo_service as rc
import ccp_service as ccp

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}

# Senda de gradualidad del IPUF* por año tarifario (m³/susc·mes), art. 2.1.2.1.2.3.
# Solo se declara la de los segmentos confirmados; para los demás se enuncia IPUF* de inicio.
SENDA_IPUF = {
    2: [6, 6, 6, 5, 5, 4],   # segundo segmento (p. ej. Las Ceibas)
}
ESTANDAR_IPUF = 4.0          # estándar de eficiencia de pérdidas (art. 2.1.2.1.2.2)
ART = {
    "ccp": "2.1.2.1.3.3", "ipuf_estrella": "2.1.2.1.3.5.2 par. 1",
    "senda": "2.1.2.1.2.3", "estandar": "2.1.2.1.2.2", "fap": "parágrafo 3 del art. del CCP",
}


def anios_con_datos(conn, empresa_id):
    """Años que tienen información comercial (suscriptores/facturación), de mayor a menor."""
    return [r[0] for r in conn.execute(text(
        "SELECT DISTINCT anio FROM carga_mensual WHERE empresa_id=:e ORDER BY anio DESC"),
        {"e": empresa_id}).all()]


def _agg(conn, empresa_id, anio):
    """Por servicio: N (Σ suscriptores-mes), AF (Σ m³ facturados), meses, y AP (Σ m³ producidos)."""
    com = conn.execute(text(
        "SELECT servicio, COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3_facturados),0) af, "
        "       COUNT(*) meses "
        "FROM carga_mensual WHERE empresa_id=:e AND anio=:a AND cod_dane='' GROUP BY servicio"),
        {"e": empresa_id, "a": anio}).mappings().all()
    mm = {r["servicio"]: float(r["ap"]) for r in conn.execute(text(
        "SELECT servicio, COALESCE(SUM(m3_producido),0) ap FROM macromedicion "
        "WHERE empresa_id=:e AND anio=:a GROUP BY servicio"), {"e": empresa_id, "a": anio}).mappings().all()}
    out = {}
    for r in com:
        s = r["servicio"]
        out[s] = {"n": float(r["n"]), "af": float(r["af"]), "meses": int(r["meses"]),
                  "ap": mm.get(s, 0.0)}
    return out


def indicadores(conn, empresa_id, anio, ipuf_estrella):
    """Indicadores y CCP por servicio para el año base dado."""
    datos = _agg(conn, empresa_id, anio)
    res = {}
    for s, d in datos.items():
        n, af, ap = d["n"], d["af"], d["ap"]
        fila = {"anio": anio, "meses": d["meses"], "n": n, "af": af, "ap": ap,
                "icuf": None, "ipuf_real": None, "isuf": None,
                "perdidas_reales": None, "estandar": None, "reconocidas": None,
                "ipuf_aplicado": None, "ccp": None, "fap": None, "isuf_ajustado": None,
                "usa_ap": ap > 0, "falta": []}
        if n <= 0:
            fila["falta"].append("suscriptores (Σ suscriptores-mes = 0)")
        if af <= 0:
            fila["falta"].append("m³ facturados")
        if n > 0:
            fila["icuf"] = af / n
        # pérdidas / IPUF solo con macromedición de producción (típico de acueducto)
        if ap > 0 and n > 0:
            fila["ipuf_real"] = (ap - af) / n
            fila["isuf"] = ap / n
            fila["perdidas_reales"] = max(ap - af, 0.0)
            fila["estandar"] = ipuf_estrella * n
            fila["reconocidas"] = min(fila["perdidas_reales"], fila["estandar"])
            fila["ipuf_aplicado"] = fila["reconocidas"] / n
            fila["ccp"] = af + fila["reconocidas"]
        elif af > 0:
            # sin AP (p. ej. alcantarillado): el CCP no corrige; el denominador es AF
            fila["ccp"] = af
            if s.lower().startswith("acu"):
                fila["falta"].append("m³ producidos (macromedición)")
        # Fap (ajuste optativo del ISUF)
        f = ccp.get(conn, empresa_id, s)
        if f and f["fap"] is not None:
            fila["fap"] = float(f["fap"])
            fila["fap_meta"] = {"ivh": f["ivh"], "metodologia": f["metodologia"],
                                "cumplio_meta": f["cumplio_meta"], "ipuf_real_fap": f["ipuf_real"],
                                "aplica": f["aplica"]}
            if fila["isuf"] is not None and f["aplica"]:
                fila["isuf_ajustado"] = fila["isuf"] - float(f["fap"])
        res[s] = fila
    return res


def senda(conn, empresa_id):
    """Senda del IPUF* por año tarifario según el segmento (período de inicio + 6 años)."""
    seg = conn.execute(text("SELECT segmento_id FROM empresa WHERE id=:e"),
                       {"e": empresa_id}).scalar()
    ipuf_ini = rc.ipuf_estrella(conn, empresa_id)
    s = SENDA_IPUF.get(seg)
    filas = [{"periodo": "Período de inicio", "anio": "jul–dic 2026", "ipuf": ipuf_ini,
              "calculado": True}]
    if s:
        for i, v in enumerate(s, start=1):
            filas.append({"periodo": f"Año tarifario {i}", "anio": str(2026 + i),
                          "ipuf": float(v), "calculado": False})
        conocida = True
    else:
        conocida = False
    return {"segmento": seg, "filas": filas, "conocida": conocida,
            "estandar": ESTANDAR_IPUF, "ipuf_inicio": ipuf_ini}


def _poly(valores, vmin, vmax, w=100.0, h=36.0, pad=3.0):
    """Puntos 'x,y …' para una polilínea SVG (viewBox w×h, y invertido)."""
    n = len(valores)
    if n == 0:
        return ""
    span = (vmax - vmin) or 1.0
    if n == 1:
        y = h - pad - (valores[0] - vmin) / span * (h - 2 * pad)
        return f"0,{y:.2f} {w:.2f},{y:.2f}"
    out = []
    for i, v in enumerate(valores):
        x = i / (n - 1) * w
        y = h - pad - (v - vmin) / span * (h - 2 * pad)
        out.append(f"{x:.2f},{y:.2f}")
    return " ".join(out)


def serie_mensual(conn, empresa_id, servicio):
    """Serie mensual (cronológica) de AF, AP y los indicadores ICUF/IPUF/ISUF del servicio,
    con las polilíneas SVG listas para graficar. El total/N usa el conjunto (cod_dane='')."""
    com = {(r["anio"], r["mes"]): (float(r["n"] or 0), float(r["af"] or 0)) for r in conn.execute(text(
        "SELECT anio, mes, COALESCE(suscriptores,0) n, COALESCE(m3_facturados,0) af "
        "FROM carga_mensual WHERE empresa_id=:e AND servicio=:s AND cod_dane=''"),
        {"e": empresa_id, "s": servicio}).mappings().all()}
    mm = {(r["anio"], r["mes"]): float(r["ap"] or 0) for r in conn.execute(text(
        "SELECT anio, mes, COALESCE(SUM(m3_producido),0) ap FROM macromedicion "
        "WHERE empresa_id=:e AND servicio=:s GROUP BY anio, mes"),
        {"e": empresa_id, "s": servicio}).mappings().all()}
    pers = sorted(set(com) | set(mm))
    if not pers:
        return None
    af = [com.get(k, (0, 0))[1] for k in pers]
    ap = [mm.get(k, 0.0) for k in pers]
    n = [com.get(k, (0, 0))[0] for k in pers]
    icuf = [(af[i] / n[i]) if n[i] else 0.0 for i in range(len(pers))]
    ipuf = [((ap[i] - af[i]) / n[i]) if (n[i] and ap[i] > 0) else 0.0 for i in range(len(pers))]
    isuf = [(ap[i] / n[i]) if (n[i] and ap[i] > 0) else 0.0 for i in range(len(pers))]
    hay_ap = any(v > 0 for v in ap)
    vmax_vol = max(max(af or [0]), max(ap or [0]), 1)
    vmax_ind = max(max(icuf or [0]), max(ipuf or [0]), max(isuf or [0]), 1)
    labels = [f"{MESES.get(m, m)}·{str(a)[2:]}" for (a, m) in pers]
    return {
        "labels": labels, "hay_ap": hay_ap,
        "vol": {"vmax": vmax_vol,
                "af": _poly(af, 0, vmax_vol), "ap": _poly(ap, 0, vmax_vol),
                "af_ult": af[-1], "ap_ult": ap[-1]},
        "ind": {"vmax": vmax_ind,
                "icuf": _poly(icuf, 0, vmax_ind), "ipuf": _poly(ipuf, 0, vmax_ind),
                "isuf": _poly(isuf, 0, vmax_ind),
                "icuf_ult": icuf[-1], "ipuf_ult": ipuf[-1], "isuf_ult": isuf[-1]},
    }


def resumen(conn, empresa_id, anio=None):
    """Paquete completo para la vista CCP."""
    anios = anios_con_datos(conn, empresa_id)
    if anio is None:
        anio = anios[0] if anios else None
    ipuf_estrella = rc.ipuf_estrella(conn, empresa_id)
    ind = indicadores(conn, empresa_id, anio, ipuf_estrella) if anio else {}
    series = {s: serie_mensual(conn, empresa_id, s) for s in ind.keys()}
    return {"anio": anio, "anios": anios, "ipuf_estrella": ipuf_estrella,
            "indicadores": ind, "series": series, "senda": senda(conn, empresa_id), "art": ART}
