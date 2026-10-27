# -*- coding: utf-8 -*-
"""Vista «Costo de referencia» — memoria de cálculo por componente (CMA / CMO / CMI / CMICT).

Para cada componente y servicio muestra: la FÓRMULA de la Res. CRA 1032, las VARIABLES que la
alimentan (con su valor, unidad, fuente y artículo) y el RESULTADO (recalculado con esas variables
y, si existe, el almacenado en `resultado_componente`).

Las variables se arman de lo que la empresa ya cargó (no se inventan):
  · numeradores CACe/COCe/CE/CIQ/COIR/ICTA/ITO/TA → del balance clasificado (numerador_subcomp),
    con CE/CIQ del módulo de energía/químicos cuando está cargado;
  · N → suscriptores promedio (comercial);
  · kct, Fa_*, CCP, CMI, denominador → de `base_calculo` (base del estudio) cuando está disponible.
Lo que falte se marca como «por cargar/calcular», con el artículo y para qué se necesita.
"""
from sqlalchemy import text
import balance_view as bv
import energia_quimicos_service as eq
import ingesta
import periodos as per

COMPS = ["CMA", "CMO", "CMI", "CMICT"]
COMP_NOMBRE = {"CMA": "Costo Medio de Administración", "CMO": "Costo Medio de Operación",
               "CMI": "Costo Medio de Inversión",
               "CMICT": "Costo Medio de Impuestos, Contribuciones y Tasas"}
COMP_ART = {"CMA": "2.1.2.1.3.2.1", "CMO": "2.1.2.1.3.4.1", "CMI": "2.1.2.1.3.5.1", "CMICT": "2.1.2.1.3.6.1"}
COMP_UNIDAD = {"CMA": "$/susc·mes", "CMO": "$/m³", "CMI": "$/m³", "CMICT": "$/m³"}
COMP_FORMULA = {
    "CMA": "CMA = CACe · (1 + k_ct) / (N · 12) · Fa_cma",
    "CMO": "CMO = (COCe + CE + CIQ + COIR) · (1 + k_ct) / CCP · Fa_cmo",
    "CMI": "CMI = (de la Base de Capital Regulado BCR₀ y el POIR)",
    "CMICT": "CMICT = (ICTA + ITO + TA) · (1 + k_ct) / D · Fa_cmict",
}
COMP_NOTA = {
    "CMA": "Numerador administrativo reconocido (CACe) por suscriptor-mes, con capital de trabajo y actualización.",
    "CMO": "Costo operativo comparable (COCe) más los particulares de energía (CE) e insumos químicos (CIQ) y el COIR, sobre el consumo corregido por pérdidas (CCP).",
    "CMI": "Se reconoce a partir de la base de capital regulado y el plan de obras e inversiones; aquí se muestra el CMI por m³ resultante.",
    "CMICT": "Impuestos, contribuciones y tasas, sobre el denominador del componente (D = CCP en acueducto; AF en alcantarillado).",
}
# Variables de cada componente (en el orden de la fórmula).
COMP_VARS = {
    "CMA": ["CACe", "kct", "N", "Fa_cma"],
    "CMO": ["COCe", "CE", "CIQ", "COIR", "kct", "CCP", "Fa_cmo"],
    "CMI": ["CMI_base"],
    "CMICT": ["ICTA", "ITO", "TA", "kct", "denom_cmict", "Fa_cmict"],
}
VAR_META = {
    "CACe": ("CACe — numerador administrativo eficiente", "$/año", "2.1.2.1.3.2.4"),
    "COCe": ("COCe — costo operativo comparable eficiente", "$/año", "2.1.2.1.3.4.4"),
    "CE": ("CE — energía eléctrica (reconocida)", "$/año", "2.1.2.1.3.4.6"),
    "CIQ": ("CIQ — insumos químicos", "$/año", "2.1.2.1.3.4.7"),
    "COIR": ("COIR — inversiones ambientales y gestión del riesgo", "$/año", "2.1.2.1.3.4.8"),
    "kct": ("k_ct — tasa de capital de trabajo", "factor", "2.1.2.1.3.1.8"),
    "N": ("N — suscriptores (promedio)", "suscriptores", "2.1.2.1.3.2.1"),
    "CCP": ("CCP — consumo corregido por pérdidas", "m³/año", "2.1.2.1.3.3.1"),
    "Fa_cma": ("Fa_cma — factor de actualización del CMA", "factor", "2.1.2.1.5.3.1"),
    "Fa_cmo": ("Fa_cmo — factor de actualización del CMO", "factor", "2.1.2.1.5.3.1"),
    "Fa_cmict": ("Fa_cmict — factor de actualización del CMICT", "factor", "2.1.2.1.5.3.1"),
    "ICTA": ("ICTA — impuestos, contribuciones y tasas admin.", "$/año", "2.1.2.1.3.6.3"),
    "ITO": ("ITO — impuestos y tasas operativos", "$/año", "2.1.2.1.3.6.4"),
    "TA": ("TA — tasas ambientales (TUA / retributiva)", "$/año", "2.1.2.1.3.6.1"),
    "denom_cmict": ("D — denominador (CCP acueducto / AF alcantarillado)", "m³/año", "2.1.2.1.3.6.1"),
    "CMI_base": ("CMI — costo medio de inversión (BCR₀ / POIR)", "$/m³", "2.1.2.1.3.5"),
}
# Subcomponentes del balance que alimentan cada numerador (numerador_subcomp).
_SUB_CACe = lambda sc: sc.startswith("CAC-") and not sc.endswith("-X")
_SUB_COCe = lambda sc: sc in ("COC-1", "COC-2", "COC-2.COM", "COC-3", "COC-4", "COC-5")


def _anios_base():
    ab = per.PERIODOS[0]["anios_base"]            # [i-2, i-1] = [2024, 2025]
    return {"CMA": ab[0], "CMO": ab[0], "CMICT": ab[-1], "CMI": ab[-1]}


def _num_por_sub(conn, empresa_id, anio):
    """numerador_subcomp del año, repartido por servicio: {servicio: {subcomponente: valor}}."""
    pct = ingesta.get_pct_ac(conn, empresa_id)
    out = {"acueducto": {}, "alcantarillado": {}}
    for r in conn.execute(text(
        "SELECT subcomponente, ac_dir, al_dir, repartir FROM numerador_subcomp "
        "WHERE empresa_id=:e AND anio=:a AND cod_dane='' ORDER BY subcomponente"),
            {"e": empresa_id, "a": anio}).mappings().all():
        ac = (r["ac_dir"] or 0.0) + (r["repartir"] or 0.0) * pct
        al = (r["al_dir"] or 0.0) + (r["repartir"] or 0.0) * (1.0 - pct)
        out["acueducto"][r["subcomponente"]] = out["acueducto"].get(r["subcomponente"], 0.0) + ac
        out["alcantarillado"][r["subcomponente"]] = out["alcantarillado"].get(r["subcomponente"], 0.0) + al
    return out


def _suscriptores(conn, empresa_id, anio):
    """N promedio mensual por servicio del año (comercial)."""
    out = {}
    for r in conn.execute(text(
        "SELECT servicio, AVG(suscriptores) AS n FROM carga_mensual "
        "WHERE empresa_id=:e AND anio=:a AND cod_dane='' AND suscriptores IS NOT NULL "
        "GROUP BY servicio"), {"e": empresa_id, "a": anio}).mappings().all():
        out[r["servicio"]] = float(r["n"]) if r["n"] is not None else None
    return out


def _base_calculo(conn, empresa_id):
    out = {}
    for r in conn.execute(text(
        "SELECT servicio, clave, valor, unidad, articulo, procedencia FROM base_calculo WHERE empresa_id=:e"),
            {"e": empresa_id}).mappings().all():
        out.setdefault(r["servicio"], {})[r["clave"]] = dict(r)
    return out


def _resultados(conn, empresa_id):
    out = {}
    for r in conn.execute(text(
        "SELECT servicio, componente, valor, unidad FROM resultado_componente WHERE empresa_id=:e"),
            {"e": empresa_id}).mappings().all():
        out.setdefault(r["servicio"], {})[r["componente"]] = dict(r)
    return out


def _val(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def variables(conn, empresa_id, servicios, emp=None):
    """Arma, por servicio, el valor y la fuente de cada variable, del mejor origen disponible."""
    ab = _anios_base()
    kct_emp = _val(emp["kct"]) if emp and emp.get("kct") is not None else None
    base = _base_calculo(conn, empresa_id)
    sub24 = _num_por_sub(conn, empresa_id, ab["CMA"])      # CACe/COCe/CE/CIQ/COIR (i-2)
    subict = _num_por_sub(conn, empresa_id, ab["CMICT"])   # ICTA/ITO/TA (i-1)
    susc = _suscriptores(conn, empresa_id, ab["CMA"])
    out = {}
    for s in servicios:
        b = base.get(s, {})

        def de_base(clave):
            r = b.get(clave)
            return (_val(r["valor"]), "base del estudio") if r and r["valor"] is not None else (None, None)

        def num(sub_map, cond):
            tot = sum(v for sc, v in sub_map.get(s, {}).items() if cond(sc))
            return tot if sub_map.get(s) else None

        v = {}

        def put(clave, valor, fuente):
            if valor is None:
                valor, fb = de_base(clave)
                fuente = fb or fuente
            v[clave] = {"valor": valor, "fuente": fuente}

        # Numeradores del balance (i-2) y de impuestos (i-1)
        cace = num(sub24, _SUB_CACe)
        coce = num(sub24, _SUB_COCe)
        coir = (sub24.get(s, {}).get("COIR") if sub24.get(s) else None)
        put("CACe", cace, "balance clasificado")
        put("COCe", coce, "balance clasificado")
        put("COIR", coir, "balance clasificado")
        # CE/CIQ: módulo de energía/químicos (reconocido); si no, el subcomponente del balance
        ce_mod, ciq_mod = eq.ce_ciq_de(conn, empresa_id, s, ab["CMO"])
        put("CE", ce_mod if ce_mod is not None else (sub24.get(s, {}).get("CE") if sub24.get(s) else None),
            "módulo de energía" if ce_mod is not None else "balance clasificado")
        put("CIQ", ciq_mod if ciq_mod is not None else (sub24.get(s, {}).get("CIQ") if sub24.get(s) else None),
            "módulo de químicos" if ciq_mod is not None else "balance clasificado")
        put("ICTA", (subict.get(s, {}).get("ICTA") if subict.get(s) else None), "balance clasificado")
        put("ITO", (subict.get(s, {}).get("ICTO") if subict.get(s) else None), "balance clasificado")
        put("TA", (subict.get(s, {}).get("TA") if subict.get(s) else None), "balance clasificado")
        put("N", susc.get(s), "comercial")
        # Parámetros regulatorios / de la base del estudio
        for clave in ("kct", "CCP", "Fa_cma", "Fa_cmo", "Fa_cmict", "denom_cmict", "CMI_base"):
            put(clave, None, None)
        if v["kct"]["valor"] is None and kct_emp is not None:
            v["kct"] = {"valor": kct_emp, "fuente": "parámetro de la empresa"}
        out[s] = v
    return out


def _calc(componente, v):
    """Recalcula el componente con las variables (o None si falta alguna requerida)."""
    g = lambda k: (v.get(k, {}) or {}).get("valor")
    kct = g("kct")
    try:
        if componente == "CMA":
            cace, n, fa = g("CACe"), g("N"), g("Fa_cma")
            if None in (cace, kct, n, fa) or not n:
                return None
            return cace * (1 + kct) / (n * 12.0) * fa
        if componente == "CMO":
            coce, ce, ciq, coir, ccp, fa = g("COCe"), g("CE"), g("CIQ"), g("COIR"), g("CCP"), g("Fa_cmo")
            partes = [coce or 0.0, ce or 0.0, ciq or 0.0, coir or 0.0]
            if coce is None or kct is None or ccp in (None, 0) or fa is None:
                return None
            return sum(partes) * (1 + kct) / ccp * fa
        if componente == "CMI":
            return g("CMI_base")
        if componente == "CMICT":
            icta, ito, ta, d, fa = g("ICTA"), g("ITO"), g("TA"), g("denom_cmict"), g("Fa_cmict")
            if None in (icta, kct, d, fa) or not d:
                return None
            return (icta + (ito or 0.0) + (ta or 0.0)) * (1 + kct) / d * fa
    except (TypeError, ZeroDivisionError):
        return None
    return None


def detalle(conn, empresa_id, componente, servicios, emp=None):
    comp = componente if componente in COMPS else "CMA"
    varset = variables(conn, empresa_id, servicios, emp=emp)
    res = _resultados(conn, empresa_id)
    por_serv = []
    for s in servicios:
        v = varset.get(s, {})
        filas = []
        for clave in COMP_VARS[comp]:
            lbl, uni, art = VAR_META.get(clave, (clave, "", ""))
            vv = v.get(clave, {})
            filas.append({"clave": clave, "label": lbl, "unidad": uni, "articulo": art,
                          "valor": vv.get("valor"), "fuente": vv.get("fuente")})
        stored = res.get(s, {}).get(comp)
        por_serv.append({
            "servicio": s, "variables": filas,
            "calc": _calc(comp, v),
            "stored": _val(stored["valor"]) if stored else None,
            "faltan": [f["label"].split(" — ")[0] for f in filas if f["valor"] is None],
        })
    return {"componentes": COMPS, "comp_nombre": COMP_NOMBRE, "componente": comp,
            "formula": COMP_FORMULA[comp], "nota": COMP_NOTA[comp], "art": COMP_ART[comp],
            "unidad": COMP_UNIDAD[comp], "por_servicio": por_serv,
            "anio_base": _anios_base()[comp]}
