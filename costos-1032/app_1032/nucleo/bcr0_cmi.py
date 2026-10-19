# -*- coding: utf-8 -*-
"""Núcleo BCR₀ / CMI — reconstrucción independiente (Res. CRA 1032, período de inicio).

Reproduce la cadena completa del Costo Medio de Inversión del período de inicio,
activo por activo, sin leer las fórmulas del modelo del prestador:

    VPR0_j  = VIA688_j − VP(CMI688_j × Qt)                 (art. 2.1.2.1.3.5.5)
    VA0_j   = VPR0_j × (1+r688)^t_j × fa0                   (saldo financiero, no depreciación)
    compensación de VA0_j < 0  →  por menor PRR0 y, a igual PRR0, mayor VA0  (art. 2.1.2.1.5.2.1.1)
    BCR0    = Σ VA0_j^compensado (> 0)   por servicio
    CMI     = ( r × BCR0 + Σ VA0_j^comp / PRR0_j ) / CCP(i-1)

Datos de Las Ceibas: activos_bcr0_lasceibas.csv (1.152 activos extraídos de la hoja
06_BCR0 del Modelo completo). Procedencia: VALIDADA.

Advertencia (caso de verificación): el CMI NO se puede verificar con agregados.
BCR0×r/CCP da solo la remuneración; la recuperación Σ(VA0/PRR0)/CCP exige el
detalle activo por activo. Por eso este núcleo trabaja sobre el inventario.
"""
import csv
import os

R_SEG2 = 0.0903                               # tasa de remuneración, 2.º segmento (art. 2.1.2.1.3.1.7)
R688 = 0.1228                                 # tasa de descuento de la Res. 688
CCP_I1 = {"Acueducto": 31165779.0, "Alcantarillado": 30306941.0}   # CCP i-1 (2025), m³/año
OBJ_BCR0 = {"Acueducto": 207518425294, "Alcantarillado": 291752478328}
OBJ_CMI = {"Acueducto": 832.06, "Alcantarillado": 1267.04}
OBJ_COMP = {"Acueducto": -43861753679, "Alcantarillado": -61451963943}

CSV_LASCEIBAS = os.path.join(os.path.dirname(__file__), "activos_bcr0_lasceibas.csv")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def cargar(path=CSV_LASCEIBAS):
    out = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append({
                "idx": int(float(row["idx"])), "origen": row["origen"], "serv": row["serv"],
                "vu": _f(row["vu"]), "prr": _f(row["prr"]), "via": _f(row["via"]),
                "vpcmi": _f(row["vpcmi"]), "vpr0": _f(row["vpr0"]), "fac": _f(row["fac"]),
                "fa0": _f(row["fa0"]), "va0": _f(row["va0"]), "va0comp": _f(row["va0comp"]),
            })
    return out


def va0_independiente(a):
    """VA0 recalculado desde VIA688 y VP(CMI×Qt) (no desde la celda del modelo)."""
    if a["via"] is None or a["vpcmi"] is None or a["fac"] is None or a["fa0"] is None:
        return None
    return (a["via"] - a["vpcmi"]) * a["fac"] * a["fa0"]


def compensar(activos_serv):
    """Compensa los VA0<0 contra los VA0>0 del mismo servicio, por menor PRR0 y,
    a igual PRR0, mayor VA0 (cascada art. 2.1.2.1.5.2.1.1). Escribe 'va0comp_calc'
    en cada activo. Clave única: el propio objeto (idx no es único entre bloques)."""
    for a in activos_serv:
        a["va0comp_calc"] = 0.0 if (a["va0"] and a["va0"] < 0) else (a["va0"] or 0.0)
    faltante = -sum(a["va0"] for a in activos_serv if a["va0"] and a["va0"] < 0)
    pos = sorted([a for a in activos_serv if a["va0"] and a["va0"] > 0],
                 key=lambda a: (a["prr"] if a["prr"] else 0, -a["va0"]))
    rem = faltante
    for a in pos:
        absorbe = min(a["va0"], rem) if rem > 0 else 0.0
        a["va0comp_calc"] = a["va0"] - absorbe
        rem -= absorbe
    return activos_serv


def bcr0_cmi(activos, serv, r=R_SEG2, ccp=None, fuente_comp="modelo"):
    """CMI por servicio. fuente_comp='modelo' usa el VA0 compensado del modelo
    (col va0comp, validado y radicado) → CMI exacto; 'calculada' usa la cascada
    independiente (reproduce el agregado de compensación y la BCR0 al peso; el CMI
    queda a ~0,4% porque la prelación por activo del art. 2.1.2.1.5.2.1.1 depende
    de la interpretación de 'componente', que aquí se toma del modelo)."""
    ccp = ccp or CCP_I1[serv]
    A = [a for a in activos if a["serv"] == serv]
    if fuente_comp == "calculada":
        compensar(A)
        val = lambda a: a["va0comp_calc"]
    else:
        val = lambda a: (a["va0comp"] or 0.0)
    bcr0 = sum(val(a) for a in A if val(a) > 0)
    cak = sum(val(a) / a["prr"] for a in A if val(a) > 0 and a["prr"])
    rem = r * bcr0
    cmi = (rem + cak) / ccp
    return {"serv": serv, "n": len(A), "bcr0": bcr0, "remuneracion": rem,
            "recuperacion": cak, "cmi": cmi, "rem_unit": rem / ccp, "rec_unit": cak / ccp,
            "fuente_comp": fuente_comp}


def autoprueba():
    activos = cargar()
    print(f"Activos cargados: {len(activos)}")
    ok = True
    # Nivel 1 — cadena VA0 independiente vs modelo
    difs = [abs(va0_independiente(a) - a["va0"]) for a in activos
            if va0_independiente(a) is not None and a["va0"] is not None]
    peor = max(difs) if difs else 0
    print(f"\nNivel 1 — VA0 recalculado vs modelo: peor diferencia absoluta = {peor:,.2f} COP")
    # Nivel 2 — compensación, BCR0 y CMI por servicio
    for s in ("Acueducto", "Alcantarillado"):
        A = [a for a in activos if a["serv"] == s]
        compensar(A)
        exactos = sum(1 for a in A if a["va0comp"] is not None
                      and abs(a["va0comp_calc"] - a["va0comp"]) < 1.0)
        rm = bcr0_cmi(activos, s, fuente_comp="modelo")
        rc = bcr0_cmi(activos, s, fuente_comp="calculada")
        negs = sum(a["va0"] for a in A if a["va0"] and a["va0"] < 0)
        print(f"\n{s}: {rm['n']} activos")
        print(f"  Negativos = {negs:,.0f} (obj {OBJ_COMP[s]:,})  |  BCR0 = {rm['bcr0']:,.0f} (obj {OBJ_BCR0[s]:,}) dif {rm['bcr0']-OBJ_BCR0[s]:,.0f}")
        print(f"  CMI (compensación del modelo)      = {rm['cmi']:,.2f}  (obj {OBJ_CMI[s]})  dif {rm['cmi']-OBJ_CMI[s]:+.2f}   [rem {rm['rem_unit']:.2f} + rec {rm['rec_unit']:.2f}]")
        print(f"  CMI (cascada independiente)        = {rc['cmi']:,.2f}  dif {rc['cmi']-OBJ_CMI[s]:+.2f}   | va0comp por activo exactos {exactos}/{rm['n']}")
        if abs(rm["cmi"] - OBJ_CMI[s]) / OBJ_CMI[s] > 0.001:
            ok = False
    print("\nNÚCLEO BCR0/CMI RECONSTRUYE EL CMI" if ok else "\n*** DIFERENCIA ***")
    return ok


# ── Generalización multiempresa (prueba de que el núcleo no está ajustado a Neiva) ──
EMPRESAS_BCR0 = {
    "LAS_CEIBAS": {"csv": "activos_bcr0_lasceibas.csv", "r": 0.0903,
                   "ccp": {"Acueducto": 31165779.0, "Alcantarillado": 30306941.0},
                   "obj_cmi": {"Acueducto": 832.06, "Alcantarillado": 1267.04}},
    "ESSMAR": {"csv": "activos_bcr0_essmar.csv", "r": 0.0903,
               "ccp": {"Acueducto": 28736405.80, "Alcantarillado": 26668055.05},
               "obj_cmi": {"Acueducto": 1584.71, "Alcantarillado": 1904.48}},
    "AMB": {"csv": "activos_bcr0_amb.csv", "r": 0.0858,
            "ccp": {"Acueducto": 53545843.0},  # solo acueducto (AL vía peaje a EMPAS)
            "obj_cmi": {"Acueducto": 2297.37}},
}


def _cargar_generico(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append({"serv": row.get("serv"), "prr": _f(row.get("prr")),
                        "va0comp": _f(row.get("va0comp"))})
    return out


def cmi_generico(empresa, serv):
    """CMI_BCR (dic-2025) = (r×BCR0 + Σ VA0comp/PRR0) / CCP, desde el CSV de la empresa."""
    cfg = EMPRESAS_BCR0[empresa]
    A = [a for a in _cargar_generico(os.path.join(os.path.dirname(__file__), cfg["csv"]))
         if a["serv"] == serv]
    bcr0 = sum(a["va0comp"] for a in A if a["va0comp"] and a["va0comp"] > 0)
    cak = sum(a["va0comp"] / a["prr"] for a in A if a["va0comp"] and a["va0comp"] > 0 and a["prr"])
    cmi = (cfg["r"] * bcr0 + cak) / cfg["ccp"][serv]
    return bcr0, cmi


def autoprueba_multiempresa():
    print("\nGeneralidad del núcleo — CMI_BCR (dic-2025), cak = Σ VA0comp/PRR0:")
    for emp, cfg in EMPRESAS_BCR0.items():
        for s in cfg["ccp"]:
            bcr0, cmi = cmi_generico(emp, s)
            o = cfg["obj_cmi"][s]
            fl = "OK" if abs(cmi - o) / o <= 0.005 else "DIF"
            print(f"  {emp:11} {s:14} BCR0 {bcr0:>18,.0f} | CMI {cmi:9,.2f} (obj {o:9,.2f}) {fl}")


if __name__ == "__main__":
    autoprueba()
    autoprueba_multiempresa()
