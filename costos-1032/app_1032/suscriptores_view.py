# -*- coding: utf-8 -*-
"""Dashboard de suscriptores (Resultados · primer submenú).

Análisis de la base de suscriptores a partir del detalle comercial cargado
(`carga_mensual_detalle`, que ya trae clase de uso y APS vía cod_dane):
  · evolución mensual del número de suscriptores por servicio;
  · composición por clase de uso (estrato / uso) del último período;
  · distribución por APS (municipio) del último período;
  · tasa de crecimiento anual (promedio mensual de suscriptores, año contra año).

El número de suscriptores de un mes es un stock: se SUMA sobre clases y APS de
ese mes (no se suma entre meses). No inventa datos: si no hay detalle comercial,
la vista lo indica.
"""
from sqlalchemy import text
from operacion_service import CLASES

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
# Paleta categórica (consistente, legible en claro/oscuro): acueducto / alcantarillado.
COLORES = {"acueducto": "#1f7a6b", "alcantarillado": "#b5651d"}
COLOR_SERIE = ["#1f7a6b", "#b5651d", "#3b6ea5", "#8a6d1f", "#7a4fa0", "#4a7c3f"]


def _poly(valores, vmin, vmax, w=100.0, h=36.0, pad=3.0):
    """Puntos 'x,y x,y …' para una polilínea SVG en un viewBox w×h (y invertido)."""
    n = len(valores)
    if n == 0:
        return ""
    span = (vmax - vmin) or 1.0
    if n == 1:
        y = h - pad - (valores[0] - vmin) / span * (h - 2 * pad)
        return f"0,{y:.2f} {w:.2f},{y:.2f}"
    pts = []
    for i, v in enumerate(valores):
        x = i / (n - 1) * w
        y = h - pad - (v - vmin) / span * (h - 2 * pad)
        pts.append(f"{x:.2f},{y:.2f}")
    return " ".join(pts)


def dashboard(conn, empresa_id, servicio=None, cod_dane=None):
    serv_emp = [s for (s,) in conn.execute(text(
        "SELECT DISTINCT servicio FROM carga_mensual_detalle WHERE empresa_id=:e ORDER BY servicio"),
        {"e": empresa_id}).all()]
    aps_rows = conn.execute(text(
        "SELECT DISTINCT d.cod_dane, m.nombre FROM carga_mensual_detalle d "
        "LEFT JOIN municipio m ON m.cod_dane = d.cod_dane WHERE d.empresa_id=:e ORDER BY d.cod_dane"),
        {"e": empresa_id}).all()
    aps_list = [{"cod_dane": c, "municipio": (nom or ("Conjunto" if c == "" else c))} for c, nom in aps_rows]
    hay_aps = any(c for c, _ in aps_rows)      # existe desglose por APS (algún cod_dane != '')

    filtro_serv = " AND servicio=:s" if servicio else ""
    filtro_aps = " AND cod_dane=:cd" if cod_dane is not None else ""
    p = {"e": empresa_id}
    if servicio:
        p["s"] = servicio
    if cod_dane is not None:
        p["cd"] = cod_dane

    # Suscriptores por (servicio, anio, mes) = Σ sobre clase y APS (según filtros).
    filas = conn.execute(text(
        "SELECT servicio, anio, mes, SUM(suscriptores) AS susc, SUM(m3) AS m3 "
        "FROM carga_mensual_detalle WHERE empresa_id=:e" + filtro_serv + filtro_aps + " "
        "GROUP BY servicio, anio, mes ORDER BY servicio, anio, mes"), p).mappings().all()

    series_mes = {}            # servicio -> [(anio,mes,susc)]
    periodos = []              # etiquetas (anio,mes) presentes, cronológico
    for r in filas:
        series_mes.setdefault(r["servicio"], []).append((r["anio"], r["mes"], int(r["susc"] or 0)))
        if (r["anio"], r["mes"]) not in periodos:
            periodos.append((r["anio"], r["mes"]))
    periodos.sort()

    # Gráfica de evolución mensual (SVG): una línea por servicio, eje Y compartido.
    todos_val = [v for s in series_mes.values() for (_, _, v) in s]
    vmin = 0
    vmax = max(todos_val) if todos_val else 1
    graf = {"labels": [f"{MESES.get(m, m)}·{str(a)[2:]}" for (a, m) in periodos],
            "vmax": vmax, "series": []}
    for i, (s, pts) in enumerate(sorted(series_mes.items())):
        porper = {(a, m): v for (a, m, v) in pts}
        vals = [porper.get(per, 0) for per in periodos]
        graf["series"].append({"servicio": s, "color": COLORES.get(s, COLOR_SERIE[i % len(COLOR_SERIE)]),
                               "points": _poly(vals, vmin, vmax), "ultimo": vals[-1] if vals else 0})

    # Último período con datos (global) y por servicio.
    ult = periodos[-1] if periodos else None

    # KPIs + composición por clase + por APS, del último período, por servicio.
    kpis, composicion, por_aps, crecimiento = [], {}, {}, {}
    for s in sorted(series_mes.keys()):
        pts = series_mes[s]
        ultimo_s = pts[-1] if pts else None
        # Composición por clase (último período del servicio)
        comp = []
        if ultimo_s:
            a_u, m_u, _ = ultimo_s
            rows = conn.execute(text(
                "SELECT clase, SUM(suscriptores) AS susc FROM carga_mensual_detalle "
                "WHERE empresa_id=:e AND servicio=:s AND anio=:a AND mes=:m" + filtro_aps + " "
                "GROUP BY clase ORDER BY clase"),
                {**p, "s": s, "a": a_u, "m": m_u}).mappings().all()
            tot = sum(int(r["susc"] or 0) for r in rows) or 1
            comp = [{"clase": r["clase"], "nombre": CLASES.get(r["clase"], str(r["clase"])),
                     "susc": int(r["susc"] or 0), "pct": int(r["susc"] or 0) / tot * 100.0} for r in rows]
            # Por APS (último período del servicio), solo si hay desglose
            if hay_aps:
                arows = conn.execute(text(
                    "SELECT d.cod_dane, mu.nombre AS municipio, SUM(d.suscriptores) AS susc "
                    "FROM carga_mensual_detalle d LEFT JOIN municipio mu ON mu.cod_dane=d.cod_dane "
                    "WHERE d.empresa_id=:e AND d.servicio=:s AND d.anio=:a AND d.mes=:m "
                    "GROUP BY d.cod_dane, mu.nombre ORDER BY d.cod_dane"),
                    {"e": empresa_id, "s": s, "a": a_u, "m": m_u}).mappings().all()
                tota = sum(int(r["susc"] or 0) for r in arows) or 1
                por_aps[s] = [{"cod_dane": r["cod_dane"],
                               "municipio": (r["municipio"] or ("Conjunto" if r["cod_dane"] == "" else r["cod_dane"])),
                               "susc": int(r["susc"] or 0), "pct": int(r["susc"] or 0) / tota * 100.0}
                              for r in arows]
        composicion[s] = comp
        # Crecimiento anual: promedio mensual de suscriptores por año, YoY.
        poraño = {}
        for (a, m, v) in pts:
            poraño.setdefault(a, []).append(v)
        prom = {a: (sum(vs) / len(vs)) for a, vs in poraño.items()}
        cre = []
        aa = sorted(prom)
        for j, a in enumerate(aa):
            g = None
            if j > 0 and prom[aa[j - 1]]:
                g = (prom[a] - prom[aa[j - 1]]) / prom[aa[j - 1]] * 100.0
            cre.append({"anio": a, "prom": prom[a], "crecimiento": g})
        crecimiento[s] = cre
        kpis.append({"servicio": s,
                     "ultimo": (ultimo_s[2] if ultimo_s else 0),
                     "periodo": (f"{MESES.get(ultimo_s[1], ultimo_s[1])}-{ultimo_s[0]}" if ultimo_s else "—"),
                     "crecimiento": (cre[-1]["crecimiento"] if cre else None)})

    return {"servicios": serv_emp, "aps_list": aps_list, "hay_aps": hay_aps,
            "servicio": servicio, "cod_dane": cod_dane,
            "graf": graf, "kpis": kpis, "composicion": composicion, "por_aps": por_aps,
            "crecimiento": crecimiento, "ultimo": ult, "meses": MESES,
            "hay_datos": bool(filas)}
