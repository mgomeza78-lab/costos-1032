# -*- coding: utf-8 -*-
"""Años tarifarios — definición canónica para el cargue de información (Res. CRA 1032/2026).

La metodología se aplica primero en el **período de inicio** (1-jul-2026 a 31-dic-2026) y luego
en **diez años tarifarios** (año 1 = 2027 … año 10 = 2036), horizonte del POIR. Toda la información
que se cargue (costos, volúmenes, suscriptores, avance del POIR, metas) se ata a su año tarifario,
para que el seguimiento, la indexación y los recálculos queden correctamente atribuidos.

  · Período de inicio: este estudio; el cálculo mensual es seguimiento/control.
  · Año tarifario 1 (2027): lo fija el primer recálculo (metas cuantificadas, línea base cierre 2026).
  · Años 2–10 (2028–2036): recálculos/indexación sucesivos.
"""

ANIO_INICIO = 2026          # el período de inicio ocurre en 2026 (jul–dic)
MES_INICIO = 7              # julio
N_ANIOS = 10               # años tarifarios 1..10
ANIO_BASE_A1 = 2027        # año tarifario 1 = 2027


def _periodos():
    ps = [{
        "clave": "inicio", "orden": 0, "etiqueta": "Período de inicio", "corto": "Inicio",
        "anio": ANIO_INICIO, "mes_ini": MES_INICIO, "mes_fin": 12,
        "fecha_ini": f"{ANIO_INICIO}-07-01", "fecha_fin": f"{ANIO_INICIO}-12-31",
        "es_inicio": True, "meses": 6,
    }]
    for k in range(1, N_ANIOS + 1):
        a = ANIO_BASE_A1 + (k - 1)
        ps.append({
            "clave": f"a{k}", "orden": k, "etiqueta": f"Año tarifario {k}", "corto": f"Año {k}",
            "anio": a, "mes_ini": 1, "mes_fin": 12,
            "fecha_ini": f"{a}-01-01", "fecha_fin": f"{a}-12-31",
            "es_inicio": False, "meses": 12,
        })
    return ps


PERIODOS = _periodos()
POR_ANIO = {p["anio"]: p for p in PERIODOS}      # cada año calendario mapea a un período
POR_CLAVE = {p["clave"]: p for p in PERIODOS}


def periodo_de(anio, mes=None):
    """Devuelve el período (dict) de un año/mes calendario, o None si queda fuera del horizonte
    (p. ej. ene–jun 2026, antes del inicio, o después de 2036)."""
    anio = int(anio)
    p = POR_ANIO.get(anio)
    if not p:
        return None
    if p["es_inicio"] and mes is not None and int(mes) < MES_INICIO:
        return None            # ene–jun 2026 no pertenece al período de inicio
    return p


def etiqueta(anio, mes=None):
    """Etiqueta del año tarifario de un año/mes calendario ('Período de inicio', 'Año tarifario 3')."""
    p = periodo_de(anio, mes)
    return p["etiqueta"] if p else "Fuera de horizonte"


def corto(anio, mes=None):
    p = periodo_de(anio, mes)
    return p["corto"] if p else "—"


def es_periodo_inicio(anio, mes=None):
    p = periodo_de(anio, mes)
    return bool(p and p["es_inicio"])


if __name__ == "__main__":
    print("Años tarifarios (Res. CRA 1032/2026):")
    for p in PERIODOS:
        print(f"  {p['orden']:>2}  {p['etiqueta']:<20} {p['fecha_ini']} → {p['fecha_fin']} "
              f"({p['meses']} meses)")
