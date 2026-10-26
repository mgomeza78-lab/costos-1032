# -*- coding: utf-8 -*-
"""Dashboard de suscriptores (Resultados · primer submenú).

Análisis de la base de suscriptores a partir del detalle comercial cargado
(`carga_mensual_detalle`, que ya trae clase de uso y APS vía cod_dane):
  · evolución mensual del número de suscriptores por servicio (gráfica);
  · composición por clase de uso del período elegido (suscriptores, % e ICUF);
  · distribución por APS (municipio) del período elegido;
  · tasa de crecimiento anual (promedio mensual de suscriptores, año contra año).

El número de suscriptores de un mes es un stock: se SUMA sobre clases y APS de
ese mes (no se suma entre meses). El ICUF = m³ facturados / suscriptores.
No inventa datos: si no hay detalle comercial, la vista lo indica.
"""
from sqlalchemy import text
from operacion_service import CLASES

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
COLORES = {"acueducto": "#1f7a6b", "alcantarillado": "#b5651d"}
COLOR_SERIE = ["#1f7a6b", "#b5651d", "#3b6ea5", "#8a6d1f", "#7a4fa0", "#4a7c3f"]

# Geometría de la gráfica SVG (escala uniforme, sin distorsión).
W, H, ML, MR, MT, MB = 600.0, 110.0, 44.0, 8.0, 8.0, 8.0


def _mil(v):
    try:
        return f"{int(round(v)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _rango(vals):
    """Rango del eje Y ajustado a los datos (no arranca en 0, para que se vea la variación
    de un stock casi constante). Si todo es igual, deja una banda pequeña alrededor."""
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
    pw, ph = W - ML - MR, H - MT - MB
    out = []
    for i, v in enumerate(vals):
        x = ML + (i / (n - 1) if n > 1 else 0.5) * pw
        y = MT + (1 - (v - vmin) / span) * ph
        out.append((round(x, 1), round(y, 1)))
    return out


def dashboard(conn, empresa_id, servicio=None, cod_dane=None, periodo=None):
    serv_emp = [s for (s,) in conn.execute(text(
        "SELECT DISTINCT servicio FROM carga_mensual_detalle WHERE empresa_id=:e ORDER BY servicio"),
        {"e": empresa_id}).all()]
    aps_rows = conn.execute(text(
        "SELECT DISTINCT d.cod_dane, m.nombre FROM carga_mensual_detalle d "
        "LEFT JOIN municipio m ON m.cod_dane = d.cod_dane WHERE d.empresa_id=:e ORDER BY d.cod_dane"),
        {"e": empresa_id}).all()
    aps_list = [{"cod_dane": c, "municipio": (nom or ("Conjunto" if c == "" else c))} for c, nom in aps_rows]
    hay_aps = any(c for c, _ in aps_rows)

    filtro_serv = " AND servicio=:s" if servicio else ""
    filtro_aps = " AND cod_dane=:cd" if cod_dane is not None else ""
    p = {"e": empresa_id}
    if servicio:
        p["s"] = servicio
    if cod_dane is not None:
        p["cd"] = cod_dane

    # Períodos disponibles (según filtros) para el selector y para fijar el período activo.
    pers_rows = conn.execute(text(
        "SELECT DISTINCT anio, mes FROM carga_mensual_detalle WHERE empresa_id=:e" + filtro_serv + filtro_aps + " "
        "ORDER BY anio, mes"), p).mappings().all()
    periodos = [(r["anio"], r["mes"]) for r in pers_rows]
    periodos_disp = [{"val": f"{a}-{m:02d}", "label": f"{MESES.get(m, m)}-{a}"} for (a, m) in reversed(periodos)]
    # Período activo: el pedido (si existe) o el último disponible.
    activo = None
    if periodo:
        try:
            pa, pm = periodo.split("-"); activo = (int(pa), int(pm))
        except (ValueError, AttributeError):
            activo = None
    if activo not in periodos:
        activo = periodos[-1] if periodos else None

    # Suscriptores por (servicio, anio, mes) = Σ sobre clase y APS (según filtros) → evolución.
    filas = conn.execute(text(
        "SELECT servicio, anio, mes, SUM(suscriptores) AS susc FROM carga_mensual_detalle "
        "WHERE empresa_id=:e" + filtro_serv + filtro_aps + " "
        "GROUP BY servicio, anio, mes ORDER BY servicio, anio, mes"), p).mappings().all()
    series_mes = {}
    for r in filas:
        series_mes.setdefault(r["servicio"], []).append((r["anio"], r["mes"], int(r["susc"] or 0)))

    # Gráfica de evolución (eje Y ajustado a los datos, escala uniforme).
    todos = [v for s in series_mes.values() for (_, _, v) in s]
    vmin, vmax = _rango(todos)
    graf = {"labels": [f"{MESES.get(m, m)}·{str(a)[2:]}" for (a, m) in periodos],
            "vmin": vmin, "vmax": vmax, "vmin_lbl": _mil(vmin), "vmax_lbl": _mil(vmax),
            "W": W, "H": H, "ML": ML, "MR": MR, "MT": MT, "MB": MB,
            "x0": ML, "x1": W - MR, "y0": MT, "y1": H - MB, "series": []}
    for i, (s, pts) in enumerate(sorted(series_mes.items())):
        porper = {(a, m): v for (a, m, v) in pts}
        vals = [porper.get(per, 0) for per in periodos]
        xy = _coords(vals, vmin, vmax, len(periodos))
        graf["series"].append({
            "servicio": s, "color": COLORES.get(s, COLOR_SERIE[i % len(COLOR_SERIE)]),
            "poly": " ".join(f"{x},{y}" for x, y in xy), "dots": [[x, y] for x, y in xy],
            "ultimo": vals[-1] if vals else 0})

    # Etiqueta del período activo y del ámbito.
    per_lbl = (f"{MESES.get(activo[1], activo[1])}-{activo[0]}" if activo else "—")
    aps_lbl = "todas las APS (empresa)" if cod_dane is None else (
        next((a["municipio"] for a in aps_list if a["cod_dane"] == cod_dane), cod_dane) or "conjunto")

    # KPIs + composición por clase + por APS, del PERÍODO ACTIVO, por servicio.
    kpis, composicion, por_aps, crecimiento = [], {}, {}, {}
    servicios_vista = [s for s in serv_emp if (not servicio or s == servicio)]
    for s in servicios_vista:
        # Composición por clase en el período activo (suscriptores, %, m³ e ICUF).
        comp, comp_tot = [], None
        if activo:
            a_u, m_u = activo
            rows = conn.execute(text(
                "SELECT clase, SUM(suscriptores) AS susc, SUM(m3) AS m3 FROM carga_mensual_detalle "
                "WHERE empresa_id=:e AND servicio=:s AND anio=:a AND mes=:m" + filtro_aps + " "
                "GROUP BY clase ORDER BY clase"),
                {**p, "s": s, "a": a_u, "m": m_u}).mappings().all()
            tsu = sum(int(r["susc"] or 0) for r in rows)
            tm3 = sum(float(r["m3"] or 0) for r in rows)
            for r in rows:
                su = int(r["susc"] or 0); m3 = float(r["m3"] or 0)
                comp.append({"clase": r["clase"], "nombre": CLASES.get(r["clase"], str(r["clase"])),
                             "susc": su, "pct": (su / tsu * 100.0 if tsu else 0.0),
                             "icuf": (m3 / su if su else None)})
            if tsu:
                comp_tot = {"susc": tsu, "pct": 100.0, "icuf": (tm3 / tsu if tsu else None)}
            # Por APS en el período activo (solo si hay desglose).
            if hay_aps:
                arows = conn.execute(text(
                    "SELECT d.cod_dane, mu.nombre AS municipio, SUM(d.suscriptores) AS susc, SUM(d.m3) AS m3 "
                    "FROM carga_mensual_detalle d LEFT JOIN municipio mu ON mu.cod_dane=d.cod_dane "
                    "WHERE d.empresa_id=:e AND d.servicio=:s AND d.anio=:a AND d.mes=:m "
                    "GROUP BY d.cod_dane, mu.nombre ORDER BY d.cod_dane"),
                    {"e": empresa_id, "s": s, "a": a_u, "m": m_u}).mappings().all()
                tsa = sum(int(r["susc"] or 0) for r in arows)
                tma = sum(float(r["m3"] or 0) for r in arows)
                lst = []
                for r in arows:
                    su = int(r["susc"] or 0); m3 = float(r["m3"] or 0)
                    lst.append({"cod_dane": r["cod_dane"],
                                "municipio": (r["municipio"] or ("Conjunto" if r["cod_dane"] == "" else r["cod_dane"])),
                                "susc": su, "pct": (su / tsa * 100.0 if tsa else 0.0),
                                "icuf": (m3 / su if su else None)})
                if tsa:
                    lst.append({"cod_dane": "__tot__", "municipio": "Total", "susc": tsa, "pct": 100.0,
                                "icuf": (tma / tsa if tsa else None), "total": True})
                por_aps[s] = lst
        composicion[s] = {"filas": comp, "total": comp_tot}
        # Crecimiento: promedio ANUAL (media mensual del año) + crecimiento YoY, y el crecimiento
        # PROMEDIO MENSUAL (media de las variaciones mes a mes), global y por año.
        pts = sorted(series_mes.get(s, []))            # (anio, mes, susc) cronológico
        poraño = {}
        for (a, m, v) in pts:
            poraño.setdefault(a, []).append(v)
        prom = {a: (sum(vs) / len(vs)) for a, vs in poraño.items()}
        mom_all, mom_year = [], {}
        for i in range(1, len(pts)):
            prev, cur, yr = pts[i - 1][2], pts[i][2], pts[i][0]
            if prev:
                g = (cur - prev) / prev * 100.0
                mom_all.append(g)
                mom_year.setdefault(yr, []).append(g)
        cre_mes_s = (sum(mom_all) / len(mom_all)) if mom_all else None
        cre, aa = [], sorted(prom)
        for j, a in enumerate(aa):
            g = None
            if j > 0 and prom[aa[j - 1]]:
                g = (prom[a] - prom[aa[j - 1]]) / prom[aa[j - 1]] * 100.0
            my = mom_year.get(a)
            cre.append({"anio": a, "prom": prom[a], "crecimiento": g,
                        "mom": (sum(my) / len(my)) if my else None})
        crecimiento[s] = {"filas": cre, "mom_prom": cre_mes_s,
                          "prom_ult": (prom[aa[-1]] if aa else None)}
        # KPI: total del período activo + último crecimiento anual + crecimiento promedio mensual.
        susc_act = (comp_tot["susc"] if comp_tot else 0)
        kpis.append({"servicio": s, "ultimo": susc_act, "periodo": per_lbl, "cre_mes": cre_mes_s,
                     "prom_anual": (prom[aa[-1]] if aa else None),
                     "anio_prom": (aa[-1] if aa else None),
                     "icuf": (comp_tot["icuf"] if comp_tot else None),
                     "crecimiento": (cre[-1]["crecimiento"] if cre else None)})

    return {"servicios": serv_emp, "aps_list": aps_list, "hay_aps": hay_aps,
            "servicio": servicio, "cod_dane": cod_dane, "periodo": (f"{activo[0]}-{activo[1]:02d}" if activo else ""),
            "periodos_disp": periodos_disp, "per_lbl": per_lbl, "aps_lbl": aps_lbl,
            "servicios_vista": servicios_vista,
            "graf": graf, "kpis": kpis, "composicion": composicion, "por_aps": por_aps,
            "crecimiento": crecimiento, "meses": MESES, "hay_datos": bool(filas)}
