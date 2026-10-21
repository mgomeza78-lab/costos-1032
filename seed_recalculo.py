# -*- coding: utf-8 -*-
"""Semilla del motor de recálculo mensual: parámetros/numeradores BASE por empresa y
macromedición de muestra. Los numeradores base vienen del núcleo validado
(numerador_cac_coc para Las Ceibas; componentes_cmx para ESSMAR y amb). Se ejecuta como
el rol dueño (bypassa RLS). CMI_base se toma de resultado_componente.
"""
import os
import sys
from sqlalchemy import text
from db import engine_owner

NUCLEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nucleo")
if NUCLEO not in sys.path:
    sys.path.insert(0, NUCLEO)
import numerador_cac_coc as ncc   # noqa: E402
import componentes_cmx as cmx     # noqa: E402

FA_CMICT = 1.0187   # factor de indexación del CMICT (base i-1), común a las tres

# ---------- Las Ceibas (emp 1): del reparto por servicio validado ----------
LC = ncc.PERSERVICIO_2024
def _lc_cmict_lump(obj, denom, kct):
    """Numerador CICT lumpado que reproduce el CMICT objetivo con el denom dado."""
    return obj * denom / (FA_CMICT * (1 + kct))

def base_lasceibas():
    kct = LC["kct"]
    filas = []
    # acueducto: denom CMICT = CCP; alcantarillado: denom = AF
    AF = {"ac": LC["CCP"]["ac"], "al": 20708404.0}   # AF_al del estudio (CMICT_al); AF_ac≈CCP (no se usa en ac)
    CMICT_OBJ = {"ac": 103.92, "al": 192.90}
    denom_cmict = {"ac": LC["CCP"]["ac"], "al": AF["al"]}
    for s, serv in (("ac", "acueducto"), ("al", "alcantarillado")):
        cict = _lc_cmict_lump(CMICT_OBJ[s], denom_cmict[s], kct)
        filas.append((serv, {
            "CACe": LC["CACe"][s], "COCe": LC["COCe"][s], "CE": LC["CE"][s],
            "CIQ": LC["CIQ"][s], "COIR": LC["COIR"][s],
            "ICTA": cict, "ITO": 0.0, "TA": 0.0,              # lumpado (reconstruido)
            "N": LC["N"][s], "CCP": LC["CCP"][s], "AF": AF[s],
            "denom_cmict": denom_cmict[s],
            "Fa_cma": LC["Fa_cma"], "Fa_cmo": LC["Fa_cmo"], "Fa_cmict": FA_CMICT,
            "kct": kct}))
    return filas

# ---------- ESSMAR (emp 2) y amb (emp 3): de componentes_cmx ----------
def base_desde_cmx(empresa_codigo):
    filas = []
    for (emp, serv), d in cmx.COMPONENTES.items():
        if emp != empresa_codigo:
            continue
        cma, cmo, ci = d["cma"], d["cmo"], d["cmict"]
        serv_l = serv.lower()  # 'acueducto' | 'alcantarillado'
        es_ac = serv_l.startswith("acu")
        coce = cmo["COCe"] + cmo.get("impacto", 0.0)   # el impacto normativo (SMMLV) va al COT
        filas.append((serv_l, {
            "CACe": cma["CACe"], "COCe": coce, "CE": cmo["CE"], "CIQ": cmo["CIQ"],
            "COIR": cmo["COIR"], "ICTA": ci["ICTA"], "ITO": ci["ITO"], "TA": ci["TA"],
            "N": cma["N"], "CCP": cmo["CCP"],
            "AF": ci["denom"] if not es_ac else cmo["CCP"],   # al: AF=denom; ac: informativo
            "denom_cmict": ci["denom"],
            "Fa_cma": cma["Fa"], "Fa_cmo": cmo["Fa"], "Fa_cmict": ci["Fa"],
            "kct": d["kct"]}))
    return filas

ART = {"CACe": "2.1.2.1.3.2.4", "COCe": "2.1.2.1.3.4.4", "CE": "2.1.2.1.3.4.6",
       "CIQ": "2.1.2.1.3.4.7", "COIR": "2.1.2.1.3.4.8", "ICTA": "2.1.2.1.3.6.3",
       "ITO": "2.1.2.1.3.6.4", "TA": "2.1.2.1.3.6.1", "N": "2.1.2.1.3.2.1",
       "CCP": "2.1.2.1.3.3.1", "AF": "2.1.2.1.3.3", "denom_cmict": "2.1.2.1.3.6.1",
       "Fa_cma": "2.1.2.1.5.3.1", "Fa_cmo": "2.1.2.1.5.3.1", "Fa_cmict": "2.1.2.1.5.3.1",
       "kct": "2.1.2.1.3.1.8", "CMI_base": "2.1.2.1.3.5"}

MAP = {"LAS_CEIBAS": base_lasceibas, "ESSMAR": lambda: base_desde_cmx("ESSMAR"),
       "AMB": lambda: base_desde_cmx("AMB")}


def main():
    with engine_owner.begin() as c:
        ids = {r["codigo"]: r["id"] for r in c.execute(text(
            "SELECT id, codigo FROM empresa")).mappings().all()}
        # CMI base por empresa/servicio desde resultado_componente
        cmi = {}
        for r in c.execute(text(
            "SELECT empresa_id, servicio, valor FROM resultado_componente WHERE componente='CMI'")
            ).mappings().all():
            cmi[(r["empresa_id"], r["servicio"])] = r["valor"]

        c.execute(text("TRUNCATE base_calculo, macromedicion, numerador_mensual, "
                       "costo_referencia_mensual RESTART IDENTITY"))
        total = 0
        for codigo, fn in MAP.items():
            eid = ids.get(codigo)
            if not eid:
                continue
            for serv, vals in fn():
                vals = dict(vals)
                vals["CMI_base"] = cmi.get((eid, serv), 0.0)
                for clave, valor in vals.items():
                    unidad = "$/año" if clave in ("CACe", "COCe", "CE", "CIQ", "COIR",
                                                  "ICTA", "ITO", "TA") else (
                             "m³/año" if clave in ("CCP", "AF", "denom_cmict") else (
                             "suscriptores" if clave == "N" else (
                             "$/m³" if clave == "CMI_base" else "factor")))
                    c.execute(text(
                        "INSERT INTO base_calculo(empresa_id,servicio,clave,valor,unidad,articulo,procedencia) "
                        "VALUES (:e,:s,:k,:v,:u,:art,:p) "
                        "ON CONFLICT (empresa_id,servicio,clave) DO UPDATE SET valor=excluded.valor"),
                        {"e": eid, "s": serv, "k": clave, "v": float(valor), "u": unidad,
                         "art": ART.get(clave, ""),
                         "p": "validada" if clave != "AF" or codigo != "LAS_CEIBAS" else "supuesto"})
                    total += 1

        # Macromedición de muestra: Las Ceibas acueducto, 6 meses, con pérdidas > estándar
        # (exhibe el tope IPUF*). AF mensual del cargue ≈ 1.463.017; AP con IANC ~33%.
        eid_lc = ids.get("LAS_CEIBAS")
        if eid_lc:
            for mes in (7, 8, 9, 10, 11, 12):
                c.execute(text(
                    "INSERT INTO macromedicion(empresa_id,anio,mes,servicio,punto,m3_producido,origen) "
                    "VALUES (:e,2026,:m,'acueducto','PTAP El Jardín (muestra)',2200000,'propio') "
                    "ON CONFLICT (empresa_id,anio,mes,servicio,punto) DO UPDATE SET "
                    "m3_producido=excluded.m3_producido"), {"e": eid_lc, "m": mes})
        print(f"base_calculo: {total} parámetros; macromedición de muestra sembrada.")


if __name__ == "__main__":
    main()
