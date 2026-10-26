# -*- coding: utf-8 -*-
"""Dashboard de suscriptores (Resultados · primer submenú).

Se elige un AÑO TARIFARIO y la información se muestra para los DOS años de su línea base POR
SEPARADO, para compararlos (igual que la vista CCP). Para el período de inicio esos años son 2024
y 2025. Por cada año y servicio se calcula, a partir del detalle comercial (`carga_mensual_detalle`,
que trae clase de uso y APS vía cod_dane):
  · suscriptores promedio del año (media mensual = Σ suscriptores-mes / meses con dato);
  · ICUF = m³ facturados / suscriptores-mes;
  · composición por clase de uso (suscriptores promedio, participación e ICUF);
  · distribución por APS (municipio).
Y entre los dos años, la tasa de crecimiento. Las gráficas son de BARRAS por año.
No inventa datos: si no hay detalle comercial para la ventana, la vista lo indica.
"""
from sqlalchemy import text
from operacion_service import CLASES
from ccp_view import _barras
import periodos as per

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
COL_ANIO = ["#1f7a6b", "#b5651d"]


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


def _metricas_anio(conn, empresa_id, s, a, filtro_aps, p, hay_aps):
    """Métricas de un servicio en un año base: totales, composición por clase y por APS."""
    pp = {**p, "s": s, "a": a}
    tot = conn.execute(text(
        "SELECT COALESCE(SUM(suscriptores),0) susc, COALESCE(SUM(m3),0) m3, COUNT(DISTINCT mes) meses "
        "FROM carga_mensual_detalle WHERE empresa_id=:e AND servicio=:s AND anio=:a" + filtro_aps),
        pp).mappings().first()
    meses = int(tot["meses"] or 0)
    susc = float(tot["susc"] or 0.0)
    m3 = float(tot["m3"] or 0.0)
    prom = (susc / meses) if meses else None
    icuf = (m3 / susc) if susc else None
    comp = []
    for r in conn.execute(text(
        "SELECT clase, SUM(suscriptores) susc, SUM(m3) m3, COUNT(DISTINCT mes) meses "
        "FROM carga_mensual_detalle WHERE empresa_id=:e AND servicio=:s AND anio=:a" + filtro_aps +
        " GROUP BY clase ORDER BY clase"), pp).mappings().all():
        cs = float(r["susc"] or 0.0); cm = float(r["m3"] or 0.0); cmes = int(r["meses"] or 0)
        comp.append({"clase": r["clase"], "nombre": CLASES.get(r["clase"], str(r["clase"])),
                     "prom": (cs / cmes if cmes else 0.0),
                     "pct": (cs / susc * 100.0 if susc else 0.0),
                     "icuf": (cm / cs if cs else None)})
    aps = []
    if hay_aps:
        for r in conn.execute(text(
            "SELECT d.cod_dane, mu.nombre municipio, SUM(d.suscriptores) susc, "
            "COUNT(DISTINCT d.mes) meses FROM carga_mensual_detalle d "
            "LEFT JOIN municipio mu ON mu.cod_dane=d.cod_dane "
            "WHERE d.empresa_id=:e AND d.servicio=:s AND d.anio=:a "
            "GROUP BY d.cod_dane, mu.nombre ORDER BY d.cod_dane"),
            {"e": empresa_id, "s": s, "a": a}).mappings().all():
            cs = float(r["susc"] or 0.0); cmes = int(r["meses"] or 0)
            aps.append({"cod_dane": r["cod_dane"],
                        "municipio": (r["municipio"] or ("Conjunto" if r["cod_dane"] == "" else r["cod_dane"])),
                        "prom": (cs / cmes if cmes else 0.0),
                        "pct": (cs / susc * 100.0 if susc else 0.0)})
    return {"meses": meses, "susc": susc, "m3": m3, "prom": prom, "icuf": icuf,
            "comp": comp, "aps": aps}


def dashboard(conn, empresa_id, servicio=None, cod_dane=None, per_clave=None):
    serv_emp = [s for (s,) in conn.execute(text(
        "SELECT DISTINCT servicio FROM carga_mensual_detalle WHERE empresa_id=:e ORDER BY servicio"),
        {"e": empresa_id}).all()]
    aps_rows = conn.execute(text(
        "SELECT DISTINCT d.cod_dane, m.nombre FROM carga_mensual_detalle d "
        "LEFT JOIN municipio m ON m.cod_dane = d.cod_dane WHERE d.empresa_id=:e ORDER BY d.cod_dane"),
        {"e": empresa_id}).all()
    aps_list = [{"cod_dane": c, "municipio": (nom or ("Conjunto" if c == "" else c))} for c, nom in aps_rows]
    hay_aps = any(c for c, _ in aps_rows)

    sel = per.POR_CLAVE.get(per_clave) or per.POR_CLAVE["inicio"]
    anios_base = sel["anios_base"]
    anio_cols = [{"anio": a} for a in anios_base]

    filtro_aps = " AND cod_dane=:cd" if cod_dane is not None else ""
    base_p = {"e": empresa_id}
    if cod_dane is not None:
        base_p["cd"] = cod_dane
    servicios_vista = [s for s in serv_emp if (not servicio or s == servicio)]

    por_anio = {a: {} for a in anios_base}
    for a in anios_base:
        for s in servicios_vista:
            por_anio[a][s] = _metricas_anio(conn, empresa_id, s, a, filtro_aps, base_p, hay_aps)

    # Crecimiento del promedio anual entre los dos años base, por servicio.
    crec = {}
    y0, y1 = anios_base[0], anios_base[-1]
    for s in servicios_vista:
        p0 = (por_anio[y0].get(s) or {}).get("prom")
        p1 = (por_anio[y1].get(s) or {}).get("prom")
        crec[s] = ((p1 - p0) / p0 * 100.0) if (p0 and p1) else None

    # Gráficas de barras por año: suscriptores promedio e ICUF, agrupadas por servicio.
    grupos = [s.capitalize() for s in servicios_vista] or ["—"]
    ser_prom = [{"name": str(a), "color": COL_ANIO[i % len(COL_ANIO)],
                 "vals": [(por_anio[a].get(s) or {}).get("prom") for s in servicios_vista]}
                for i, a in enumerate(anios_base)]
    ser_icuf = [{"name": str(a), "color": COL_ANIO[i % len(COL_ANIO)],
                 "vals": [(por_anio[a].get(s) or {}).get("icuf") for s in servicios_vista]}
                for i, a in enumerate(anios_base)]
    barras = {"prom": _barras(grupos, ser_prom, _mil), "icuf": _barras(grupos, ser_icuf, _dec)}

    # Composición por clase y distribución por APS, alineadas por los DOS años (para comparar).
    comp_cmp, aps_cmp = {}, {}
    for s in servicios_vista:
        clset = {}
        for a in anios_base:
            for c in (por_anio[a].get(s) or {}).get("comp", []):
                clset[c["clase"]] = c["nombre"]
        comp_cmp[s] = [{"clase": cl, "nombre": clset[cl],
                        "cols": {a: next((c for c in (por_anio[a].get(s) or {}).get("comp", [])
                                          if c["clase"] == cl), None) for a in anios_base}}
                       for cl in sorted(clset)]
        apset = {}
        for a in anios_base:
            for x in (por_anio[a].get(s) or {}).get("aps", []):
                apset[x["cod_dane"]] = x["municipio"]
        aps_cmp[s] = [{"cod_dane": cod, "municipio": apset[cod],
                       "cols": {a: next((x for x in (por_anio[a].get(s) or {}).get("aps", [])
                                         if x["cod_dane"] == cod), None) for a in anios_base}}
                      for cod in sorted(apset)]

    aps_lbl = "todas las APS (empresa)" if cod_dane is None else (
        next((x["municipio"] for x in aps_list if x["cod_dane"] == cod_dane), cod_dane) or "conjunto")
    hay = any((por_anio[a].get(s) or {}).get("susc") for a in anios_base for s in servicios_vista)

    return {"servicios": serv_emp, "servicio": servicio, "aps_list": aps_list, "hay_aps": hay_aps,
            "cod_dane": cod_dane, "aps_lbl": aps_lbl, "periodos": per.PERIODOS, "periodo": sel,
            "anios_base": anios_base, "anios_base_lbl": "–".join(str(a) for a in anios_base),
            "anio_cols": anio_cols, "servicios_vista": servicios_vista, "por_anio": por_anio,
            "comp_cmp": comp_cmp, "aps_cmp": aps_cmp, "crec": crec, "barras": barras,
            "hay_datos": hay, "meses": MESES}
