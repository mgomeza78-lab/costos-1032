# -*- coding: utf-8 -*-
"""Índices macro para la indexación tarifaria.

Mensuales (número índice, misma grilla año/mes en la tabla ``indice_ipc``):
  · IPC            — columna ``indice``
  · IPC-SAR        — columna ``ipcs``   (IPC sin alimentos ni regulados)
  · ICTC           — columna ``ictc``   (Índice de Costos del Transporte de Carga)
Anual:
  · Salario mínimo — tabla ``salario_minimo`` (se modifica una vez al año).

Este módulo solo LEE los índices y calcula variaciones (mensual, año corrido,
anual) y la serie para la gráfica; la carga la hacen las rutas de ``main.py``.
No inventa datos: si un índice no está cargado, devuelve vacío.
"""
from datetime import date
from sqlalchemy import text

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}

# clave/columna -> (etiqueta corta, etiqueta larga, decimales a mostrar)
MENSUALES = {
    "indice": ("IPC", "IPC (DANE)", 2),
    "ipcs":   ("IPC-SAR", "IPC sin alimentos ni regulados", 2),
    "ictc":   ("ICTC", "ICTC · Costos de Transporte de Carga", 2),
}
ORDEN_MENSUAL = ["indice", "ipcs", "ictc"]


# --------------------------------------------------------------------- utilidades
def _mes_ant(a, m):
    return (a - 1, 12) if m == 1 else (a, m - 1)


def _var(curr, base):
    """Variación porcentual (curr/base − 1)·100, o None si no es calculable."""
    if curr is None or base in (None, 0):
        return None
    return (curr / base - 1.0) * 100.0


def _etq(a, m):
    return f"{MESES[m]}-{str(a)[2:]}"


# --------------------------------------------------------------------- series
def serie(conn, col):
    """Serie cronológica [{anio, mes, valor}] del índice mensual ``col`` (sin nulos)."""
    if col not in MENSUALES:
        return []
    rows = conn.execute(text(
        f"SELECT anio, mes, {col} AS v FROM indice_ipc "
        f"WHERE {col} IS NOT NULL ORDER BY anio, mes")).mappings().all()
    return [{"anio": r["anio"], "mes": r["mes"], "valor": float(r["v"])} for r in rows]


def ultimo_mensual(conn, col):
    """Último dato cargado del índice ``col`` + variaciones (mensual, año corrido, anual)."""
    s = serie(conn, col)
    if not s:
        return None
    idx = {(p["anio"], p["mes"]): p["valor"] for p in s}
    u = s[-1]
    a, m, v = u["anio"], u["mes"], u["valor"]
    corto, largo, dec = MENSUALES[col]
    return {
        "clave": col, "corto": corto, "largo": largo, "dec": dec,
        "anio": a, "mes": m, "etq": _etq(a, m), "valor": v, "n": len(s),
        "var_mensual": _var(v, idx.get(_mes_ant(a, m))),
        "var_anio_corrido": _var(v, idx.get((a - 1, 12))),
        "var_anual": _var(v, idx.get((a - 1, m))),
    }


def salario_serie(conn):
    """[{anio, valor, var}] del salario mínimo, con variación anual."""
    rows = conn.execute(text(
        "SELECT anio, valor, fuente, procedencia FROM salario_minimo ORDER BY anio")
    ).mappings().all()
    out, prev = [], None
    for r in rows:
        v = float(r["valor"])
        out.append({"anio": r["anio"], "valor": v, "var": _var(v, prev),
                    "fuente": r["fuente"], "procedencia": r["procedencia"]})
        prev = v
    return out


def ultimo_salario(conn):
    s = salario_serie(conn)
    return s[-1] if s else None


def resumen(conn):
    """Tarjetas de 'último dato cargado' para los cuatro índices."""
    return {
        "mensuales": [m for m in (ultimo_mensual(conn, c) for c in ORDEN_MENSUAL) if m],
        "salario": ultimo_salario(conn),
    }


# --------------------------------------------------------------------- próximos a cargar
def proximo_mes(conn):
    """(anio, mes) siguiente al último mes con cualquier dato mensual; si no hay, hoy."""
    k = conn.execute(text("SELECT max(anio * 100 + mes) FROM indice_ipc")).scalar()
    if not k:
        t = date.today()
        return (t.year, t.month)
    a, m = divmod(int(k), 100)
    return (a + 1, 1) if m == 12 else (a, m + 1)


def proximo_anio_salario(conn):
    a = conn.execute(text("SELECT max(anio) FROM salario_minimo")).scalar()
    return (int(a) + 1) if a else date.today().year


# --------------------------------------------------------------------- datos de la gráfica
def datos_grafica(conn, col, desde=None, hasta=None):
    """Puntos de la ventana [desde, hasta] con variación mensual y acumulada (%).

    · ``var_mes``  : respecto al mes inmediatamente anterior de la serie completa.
    · ``var_acum`` : respecto al punto justo anterior a ``desde`` (si existe); si no,
                     respecto al primer punto de la ventana (que queda en 0).
    desde/hasta son (anio, mes). Por defecto: desde enero del año en curso hasta el último.
    """
    corto, largo, dec = MENSUALES.get(col, ("", col, 2))
    s = serie(conn, col)
    if not s:
        return {"clave": col, "corto": corto, "largo": largo, "dec": dec,
                "puntos": [], "desde": desde, "hasta": hasta}
    if desde is None:
        desde = (date.today().year, 1)
    if hasta is None:
        hasta = (s[-1]["anio"], s[-1]["mes"])
    kd, kh = desde[0] * 100 + desde[1], hasta[0] * 100 + hasta[1]
    k = lambda p: p["anio"] * 100 + p["mes"]

    for i, p in enumerate(s):
        p["var_mes"] = _var(p["valor"], s[i - 1]["valor"]) if i > 0 else None

    base = None
    for p in s:                    # último punto antes de la ventana
        if k(p) < kd:
            base = p["valor"]
    ventana = [p for p in s if kd <= k(p) <= kh]
    if base is None and ventana:
        base = ventana[0]["valor"]
    for p in ventana:
        p["var_acum"] = _var(p["valor"], base)
        p["etq"] = _etq(p["anio"], p["mes"])

    return {"clave": col, "corto": corto, "largo": largo, "dec": dec,
            "puntos": ventana, "desde": desde, "hasta": hasta}


# --------------------------------------------------------------------- gráfica SVG
def _nice_tick(raw):
    """Paso 'bonito' (1·2·2.5·3·4·5·6·8·10 ×10^k) para un intervalo objetivo."""
    import math
    if raw <= 0:
        return 1.0
    exp = math.floor(math.log10(raw))
    f = raw / (10 ** exp)
    for c in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if f <= c * 1.0000001:
            return c * (10 ** exp)
    return 10 * (10 ** exp)


def svg_grafica(datos):
    """SVG responsivo: barras = variación mensual (%), línea = variación acumulada (%).

    Un solo eje en %, línea base en 0. Devuelve '' si no hay puntos.
    """
    pts = datos["puntos"]
    if not pts:
        return ""
    # geometría (viewBox; se escala al 100% del ancho)
    W, H = 760, 340
    mL, mR, mT, mB = 54, 20, 26, 54
    pw, ph = W - mL - mR, H - mT - mB
    n = len(pts)

    vmes = [p.get("var_mes") for p in pts]
    vacc = [p.get("var_acum") for p in pts]
    reales = [x for x in (vmes + vacc) if x is not None]
    if not reales:
        return ""
    import math
    vmax = max(reales + [0.0])
    vmin = min(reales + [0.0])
    rng = max(vmax, 0.0) - min(vmin, 0.0)
    tick = _nice_tick((rng or 1.0) / 5.0)
    top = math.ceil(max(vmax, 0.0) / tick) * tick
    bot = math.floor(min(vmin, 0.0) / tick) * tick
    if top == bot:
        top = bot + tick
    span = top - bot
    ndiv = int(round(span / tick))
    dec_ax = 0 if (tick == int(tick) and tick >= 1) else 1

    def y(v):
        return mT + ph * (top - v) / span

    def x(i):
        return mL + pw * (i + 0.5) / n

    y0 = y(0.0)
    bw = min(34, pw / n * 0.6)
    stride = max(1, -(-n // 14))   # ~14 etiquetas como máximo en el eje X

    teal, copper, grid, ink, muted = "#105060", "#8FB93C", "#D7E3E0", "#0F2E35", "#5E736E"
    out = []
    out.append(
        f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet" '
        f'role="img" font-family="Barlow,system-ui,sans-serif" style="max-width:100%">')

    # grilla horizontal + etiquetas del eje Y (en pasos 'bonitos')
    for g in range(ndiv + 1):
        gv = bot + tick * g
        gy = y(gv)
        out.append(f'<line x1="{mL}" y1="{gy:.1f}" x2="{W-mR}" y2="{gy:.1f}" '
                   f'stroke="{grid}" stroke-width="1"/>')
        out.append(f'<text x="{mL-8}" y="{gy+3.5:.1f}" text-anchor="end" font-size="11" '
                   f'fill="{muted}">{gv:.{dec_ax}f}%</text>')
    # línea del cero reforzada
    out.append(f'<line x1="{mL}" y1="{y0:.1f}" x2="{W-mR}" y2="{y0:.1f}" '
               f'stroke="#9FB4AE" stroke-width="1.5"/>')

    # barras: variación mensual
    for i, p in enumerate(pts):
        vm = p.get("var_mes")
        cx = x(i)
        # etiqueta X (mes-año); se ralea para que no se encimen
        if i % stride == 0 or i == n - 1:
            out.append(f'<text x="{cx:.1f}" y="{H-mB+16}" text-anchor="middle" font-size="10.5" '
                       f'fill="{muted}">{p["etq"]}</text>')
        if vm is None:
            continue
        yv = y(vm)
        ytop = min(yv, y0)
        hbar = abs(yv - y0)
        out.append(
            f'<rect x="{cx-bw/2:.1f}" y="{ytop:.1f}" width="{bw:.1f}" height="{hbar:.1f}" '
            f'rx="2" fill="{teal}" opacity="0.85"><title>{p["etq"]}: {vm:+.2f}% mensual</title></rect>')

    # línea: variación acumulada
    line_pts = [(x(i), y(p["var_acum"])) for i, p in enumerate(pts) if p.get("var_acum") is not None]
    if len(line_pts) >= 2:
        d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in line_pts)
        out.append(f'<path d="{d}" fill="none" stroke="{copper}" stroke-width="2.5" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
    for i, p in enumerate(pts):
        va = p.get("var_acum")
        if va is None:
            continue
        cx, cy = x(i), y(va)
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" fill="{copper}" '
                   f'stroke="#fff" stroke-width="1"><title>{p["etq"]}: {va:+.2f}% acumulado</title></circle>')
    # etiqueta del último punto acumulado
    if line_pts:
        lx, ly = line_pts[-1]
        lv = pts[-1]["var_acum"]
        out.append(f'<text x="{lx-6:.1f}" y="{ly-8:.1f}" text-anchor="end" font-size="11.5" '
                   f'font-weight="600" fill="#6F8F1E">{lv:+.2f}%</text>')

    out.append('</svg>')
    return "".join(out)
