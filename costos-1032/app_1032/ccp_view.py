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
        "FROM carga_mensual WHERE empresa_id=:e AND anio=:a GROUP BY servicio"),
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


def resumen(conn, empresa_id, anio=None):
    """Paquete completo para la vista CCP."""
    anios = anios_con_datos(conn, empresa_id)
    if anio is None:
        anio = anios[0] if anios else None
    ipuf_estrella = rc.ipuf_estrella(conn, empresa_id)
    ind = indicadores(conn, empresa_id, anio, ipuf_estrella) if anio else {}
    return {"anio": anio, "anios": anios, "ipuf_estrella": ipuf_estrella,
            "indicadores": ind, "senda": senda(conn, empresa_id), "art": ART}
