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
import periodos as per

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


def _agg(conn, empresa_id, anios):
    """Por servicio, agregando sobre la VENTANA de años base `anios` (lista): N (Σ suscriptores-mes),
    AF (Σ m³ facturados), meses con dato, y AP (Σ m³ producidos). Para el período de inicio la ventana
    es [2024, 2025], así que se suma sobre los dos años (art. de la línea base, Res. 1032)."""
    anios = list(anios or [])
    if not anios:
        return {}
    com = conn.execute(text(
        "SELECT servicio, COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3_facturados),0) af, "
        "       COUNT(*) meses "
        "FROM carga_mensual WHERE empresa_id=:e AND anio = ANY(:aa) AND cod_dane='' GROUP BY servicio"),
        {"e": empresa_id, "aa": anios}).mappings().all()
    mm = {r["servicio"]: float(r["ap"]) for r in conn.execute(text(
        "SELECT servicio, COALESCE(SUM(m3_producido),0) ap FROM macromedicion "
        "WHERE empresa_id=:e AND anio = ANY(:aa) GROUP BY servicio"),
        {"e": empresa_id, "aa": anios}).mappings().all()}
    out = {}
    for r in com:
        s = r["servicio"]
        out[s] = {"n": float(r["n"]), "af": float(r["af"]), "meses": int(r["meses"]),
                  "ap": mm.get(s, 0.0)}
    return out


def indicadores(conn, empresa_id, anios, ipuf_estrella):
    """Indicadores y CCP por servicio para la ventana de años base dada (lista)."""
    datos = _agg(conn, empresa_id, anios)
    res = {}
    for s, d in datos.items():
        n, af, ap = d["n"], d["af"], d["ap"]
        fila = {"anios": anios, "meses": d["meses"], "n": n, "af": af, "ap": ap,
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


# Geometría de las gráficas (escala uniforme, sin distorsión).
GW, GH, GML, GMR, GMT, GMB = 600.0, 110.0, 50.0, 8.0, 8.0, 8.0


def _mil(v):
    try:
        return f"{int(round(v)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _dec(v):
    try:
        return f"{v:.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _rango(vals):
    """Rango del eje Y ajustado a los datos (no arranca en 0, para ver la variación)."""
    vals = [v for v in vals if v is not None]
    if not vals:
        return 0.0, 1.0
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return (lo * 0.97, lo * 1.03) if lo else (0.0, 1.0)
    pad = (hi - lo) * 0.18
    return max(0.0, lo - pad), hi + pad


def _coords(vals, vmin, vmax, n):
    span = (vmax - vmin) or 1.0
    pw, ph = GW - GML - GMR, GH - GMT - GMB
    out = []
    for i, v in enumerate(vals):
        x = GML + (i / (n - 1) if n > 1 else 0.5) * pw
        y = GMT + (1 - (v - vmin) / span) * ph
        out.append((round(x, 1), round(y, 1)))
    return out


def _chart(series, labels, fmt):
    """Arma una gráfica de líneas (eje ajustado). `series`: [{name,color,vals,show}]."""
    allv = [v for s in series if s["show"] for v in s["vals"]]
    vmin, vmax = _rango(allv)
    out = {"vmin": vmin, "vmax": vmax, "vmin_lbl": fmt(vmin), "vmax_lbl": fmt(vmax), "series": []}
    for s in series:
        if not s["show"]:
            continue
        xy = _coords(s["vals"], vmin, vmax, len(labels))
        out["series"].append({"name": s["name"], "color": s["color"],
                              "poly": " ".join(f"{x},{y}" for x, y in xy),
                              "dots": [[x, y] for x, y in xy],
                              "ult": s["vals"][-1] if s["vals"] else 0})
    return out


def serie_mensual(conn, empresa_id, servicio, anios=None):
    """Serie mensual (cronológica) de AF, AP y los indicadores ICUF/IPUF/ISUF del servicio, sobre la
    ventana de años base `anios` (lista; para el período de inicio, [2024, 2025]). Los meses del eje
    los define el comercial (N/AF), así que un mes con producción pero sin comercial no aparece como
    cero. El total/N usa el conjunto (cod_dane='')."""
    anios = list(anios or [])
    fa = " AND anio = ANY(:aa)" if anios else ""
    pp = {"e": empresa_id, "s": servicio}
    if anios:
        pp["aa"] = anios
    com = {(r["anio"], r["mes"]): (float(r["n"] or 0), float(r["af"] or 0)) for r in conn.execute(text(
        "SELECT anio, mes, COALESCE(suscriptores,0) n, COALESCE(m3_facturados,0) af "
        "FROM carga_mensual WHERE empresa_id=:e AND servicio=:s AND cod_dane=''" + fa), pp).mappings().all()}
    mm = {(r["anio"], r["mes"]): float(r["ap"] or 0) for r in conn.execute(text(
        "SELECT anio, mes, COALESCE(SUM(m3_producido),0) ap FROM macromedicion "
        "WHERE empresa_id=:e AND servicio=:s" + fa + " GROUP BY anio, mes"), pp).mappings().all()}
    pers = sorted(com)        # el eje lo define el comercial (evita meses fantasma en cero)
    if not pers:
        return None
    af = [com.get(k, (0, 0))[1] for k in pers]
    ap = [mm.get(k, 0.0) for k in pers]
    n = [com.get(k, (0, 0))[0] for k in pers]
    icuf = [(af[i] / n[i]) if n[i] else 0.0 for i in range(len(pers))]
    ipuf = [((ap[i] - af[i]) / n[i]) if (n[i] and ap[i] > 0) else 0.0 for i in range(len(pers))]
    isuf = [(ap[i] / n[i]) if (n[i] and ap[i] > 0) else 0.0 for i in range(len(pers))]
    hay_ap = any(v > 0 for v in ap)
    labels = [f"{MESES.get(m, m)}·{str(a)[2:]}" for (a, m) in pers]
    return {
        "labels": labels, "hay_ap": hay_ap,
        "W": GW, "H": GH, "x0": GML, "x1": GW - GMR, "y0": GMT, "y1": GH - GMB,
        "vol": _chart([{"name": "Producida", "color": "#3b6ea5", "vals": ap, "show": hay_ap},
                       {"name": "Facturada", "color": "#1f7a6b", "vals": af, "show": True}], labels, _mil),
        "ind": _chart([{"name": "ICUF", "color": "#1f7a6b", "vals": icuf, "show": True},
                       {"name": "IPUF", "color": "#b5651d", "vals": ipuf, "show": hay_ap},
                       {"name": "ISUF", "color": "#7a4fa0", "vals": isuf, "show": hay_ap}], labels, _dec),
    }


def resumen(conn, empresa_id, per_clave=None):
    """Paquete completo para la vista CCP, por AÑO TARIFARIO. El período seleccionado define su
    ventana de años base (el de inicio = 2024–2025) y toda la información se calcula sobre ella."""
    anios_data = set(anios_con_datos(conn, empresa_id))
    # Años tarifarios ofrecidos: los que tienen algún año base con datos; siempre el de inicio.
    con_datos = [p for p in per.PERIODOS if set(p["anios_base"]) & anios_data]
    # Siempre se ofrece el período de inicio; además, los años tarifarios con datos.
    opts = ([per.PERIODOS[0]] + [p for p in con_datos if p["clave"] != "inicio"]) if con_datos \
        else [per.PERIODOS[0]]
    default = con_datos[0] if con_datos else opts[0]
    sel = next((p for p in opts if p["clave"] == per_clave), None) or default
    anios_base = sel["anios_base"]
    lbl = "–".join(str(a) for a in anios_base)
    ipuf_estrella = rc.ipuf_estrella(conn, empresa_id)
    ind = indicadores(conn, empresa_id, anios_base, ipuf_estrella)
    series = {s: serie_mensual(conn, empresa_id, s, anios_base) for s in ind.keys()}
    return {"periodo": sel, "periodos": opts, "anios_base": anios_base, "anios_base_lbl": lbl,
            "anio": lbl, "ipuf_estrella": ipuf_estrella, "indicadores": ind, "series": series,
            "senda": senda(conn, empresa_id), "art": ART}
