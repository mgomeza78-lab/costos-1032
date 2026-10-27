# -*- coding: utf-8 -*-
"""Vista del Balance de Prueba clasificado (Res. CRA 1032).

Muestra, por COMPONENTE (CMA / CMO / CMICT), el desglose por SUBCOMPONENTE y por AÑO base cargado,
con el reparto por servicio: la clase 5 (CMA e impuestos administrativos) se reparte por un %
Ac/Al editable; la clase 7 (CMO) va al servicio de cada cuenta (contabilidad separada). El período
de la línea base es el AÑO; el balance trae saldos acumulados, así que el valor por año ya es el
acumulado del período. Fuente: `numerador_subcomp` (cubetas ac_dir/al_dir/repartir)."""
from sqlalchemy import text
from ingesta import get_pct_ac

COMPONENTES = ["CMA", "CMO", "CMICT"]
COMP_NOMBRE = {"CMA": "Costo Medio de Administración", "CMO": "Costo Medio de Operación",
               "CMICT": "Costo Medio de Impuestos, Contribuciones y Tasas"}
ART = {"CMA": "2.1.2.1.3.2.4", "CMO": "2.1.2.1.3.4.4", "CMICT": "2.1.2.1.3.6"}
SUBCOMP_LABEL = {
    "CAC-1": "Beneficios a empleados (admin.)",
    "CAC-2": "Costos generales (admin.)",
    "CAC-2.COM": "Comercialización (lectura y entrega de facturas)",
    "CAC-3": "Otros administrativos reconocidos",
    "COC-1": "Beneficios a empleados (operación)",
    "COC-2": "Costos generales (operación)",
    "COC-3": "Operativos (grupo 3)", "COC-4": "Tratamiento de aguas residuales",
    "COC-5": "Operación FNCER",
    "CE": "Energía (costo particular)",
    "CIQ": "Insumos químicos (costo particular)",
    "COIR": "Inversiones ambientales y gestión del riesgo",
    "ICTA": "Impuestos y contribuciones (ICTA)",
    "ICTO": "Impuestos operativos (ICTO)",
    "TA": "Tasas ambientales (TUA / retributiva)",
}


def resumen(conn, empresa_id, componente=None, servicio=None):
    pct_ac = get_pct_ac(conn, empresa_id)
    anios = [r[0] for r in conn.execute(text(
        "SELECT DISTINCT anio FROM numerador_subcomp WHERE empresa_id=:e ORDER BY anio"),
        {"e": empresa_id}).all()]
    comp_sel = componente if componente in COMPONENTES else "CMA"
    serv_sel = servicio if servicio in ("acueducto", "alcantarillado") else "conjunto"

    rows = conn.execute(text(
        "SELECT anio, subcomponente, ac_dir, al_dir, repartir FROM numerador_subcomp "
        "WHERE empresa_id=:e AND componente=:c AND cod_dane='' ORDER BY subcomponente, anio"),
        {"e": empresa_id, "c": comp_sel}).mappings().all()

    def _val(ac, al):
        return ac if serv_sel == "acueducto" else al if serv_sel == "alcantarillado" else ac + al

    data = {}
    tot_anio = {a: 0.0 for a in anios}
    for r in rows:
        ac = (r["ac_dir"] or 0.0) + (r["repartir"] or 0.0) * pct_ac
        al = (r["al_dir"] or 0.0) + (r["repartir"] or 0.0) * (1.0 - pct_ac)
        v = _val(ac, al)
        data.setdefault(r["subcomponente"], {})[r["anio"]] = v
        tot_anio[r["anio"]] += v

    filas = []
    for sc in sorted(data):
        cols = {a: data[sc].get(a) for a in anios}
        suma = sum(v for v in cols.values() if v is not None)
        filas.append({"sub": sc, "nombre": SUBCOMP_LABEL.get(sc, sc), "cols": cols, "suma": suma})
    total_suma = sum(tot_anio.values())
    # ¿el componente tiene clase 5 (reparto por %)? CMO no; CMA y CMICT sí.
    usa_pct = comp_sel in ("CMA", "CMICT")
    return {"componentes": COMPONENTES, "comp_nombre": COMP_NOMBRE, "componente": comp_sel,
            "servicio": serv_sel, "anios": anios, "filas": filas, "total": tot_anio,
            "total_suma": total_suma, "pct_ac": pct_ac, "pct_al": 1.0 - pct_ac,
            "usa_pct": usa_pct, "hay_datos": bool(anios), "art": ART.get(comp_sel, "")}
