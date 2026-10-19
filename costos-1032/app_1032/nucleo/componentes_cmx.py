# -*- coding: utf-8 -*-
"""Cobertura de componentes CMA / CMO / CMICT (base dic-2025) — ESSMAR y amb.

Completa la reconciliación del núcleo con los componentes de cargo por consumo y
cargo fijo distintos del CMI (que lo cubre bcr0_cmi.py). Reproduce, desde los
numeradores del modelo de cada empresa, los valores dic-2025 reportados:

  CMA    = CACe × (1+kct) / (N × 12) × Fa_cma                  (art. 2.1.2.1.3.2.1)
  CMO    = (COCe + CE + CIQ + COIR) × (1+kct) / CCP × Fa_cmo   (art. 2.1.2.1.3.4.1)
  CMICT  = (ICTA + ITO + TA) × (1+kct) / denom × Fa_cmict      (art. 2.1.2.1.3.6.1)
           (denom = CCP en acueducto; AF en alcantarillado)

Las Ceibas ya está cubierta (numerador_cac_coc.py para CMA/CMO y el motor para
CMICT). Aquí se agregan ESSMAR (2.º seg., ac+al) y amb (1.er seg., solo ac).
Valores en pesos de cada año base; los cargos radicados indexados = estos × faep0.
"""

# Numeradores por empresa y servicio (del modelo recalculado de cada empresa).
COMPONENTES = {
    ("ESSMAR", "Acueducto"): {"kct": 0.0154,
        "cma": {"CACe": 10639001426.16, "N": 124847.33, "Fa": 1.06727106506171, "obj": 7695.77},
        "cmo": {"COCe": 18117293825.32, "CE": 3576220648.28, "CIQ": 3395217675.43, "COIR": 0,
                "CCP": 25603905.20, "Fa": 1.06727106506171, "obj": 1061.90},
        "cmict": {"ICTA": 2358827081.58, "ITO": 146527444.65, "TA": 116907443.70,
                  "denom": 28736405.80, "Fa": 1.0187, "obj": 94.39}},
    ("ESSMAR", "Alcantarillado"): {"kct": 0.0154,
        "cma": {"CACe": 6706770944.89, "N": 118665.0, "Fa": 1.06727106506171, "obj": 5104.13},
        "cmo": {"COCe": 12383336135.19, "CE": 2341463396.52, "CIQ": 0, "COIR": 0,
                "CCP": 23653949.77, "Fa": 1.06727106506171, "obj": 674.62},
        "cmict": {"ICTA": 2080026072.11, "ITO": 560715179.65, "TA": 2859238324.40,
                  "denom": 12966468.0, "Fa": 1.0187, "obj": 438.75}},  # denom = AF (alcantarillado)
    ("AMB", "Acueducto"): {"kct": 0.0178,
        "cma": {"CACe": 32074141441.62, "N": 322007.83, "Fa": 1.06727106506171, "obj": 9016.64},
        "cmo": {"COCe": 85094645944.02, "CE": 16556091865.36, "CIQ": 3954096154.82, "COIR": 0,
                "impacto": 5098470860.57,  # impacto normativo SMMLV al 50% (hoja 05_CMO IV)
                "CCP": 51468023.0, "Fa": 1.06727106506171, "obj": 2336.47},
        # El modelo suma el impuesto de vehículos DOS veces en el CICT (hallazgo
        # CMICT!D33, $7.211.168). Se reproduce el modelo (obj 101.68) y se marca
        # el valor limpio. Además, el impuesto de vehículos no está en la lista
        # taxativa del art. 2.1.2.1.3.6.4 — excluirlo del todo da aún menos.
        "cmict": {"ICTA": 2468873438.72, "ITO": 2387708741.25, "TA": 387455138.0,
                  "doble_conteo_vehiculos": 7211168.0, "denom": 53545833.0,
                  "Fa": 1.0187, "obj": 101.68}},
}


def cma(d):
    c = d["cma"]
    return c["CACe"] * (1 + d["kct"]) / (c["N"] * 12) * c["Fa"]


def cmo(d):
    c = d["cmo"]
    cot = (c["COCe"] + c["CE"] + c["CIQ"] + c["COIR"] + c.get("impacto", 0.0)) * (1 + d["kct"])
    return cot / c["CCP"] * c["Fa"]


def cmict(d, con_doble_conteo=True):
    c = d["cmict"]
    cict = c["ICTA"] + c["ITO"] + c["TA"]
    if con_doble_conteo:
        cict += c.get("doble_conteo_vehiculos", 0.0)
    return cict * (1 + d["kct"]) / c["denom"] * c["Fa"]


def autoprueba():
    print("Cobertura de componentes (base dic-2025) — reproducción desde numeradores:\n")
    ok = True
    for (emp, serv), d in COMPONENTES.items():
        for comp, fn, obj in (("CMA", cma, d["cma"]["obj"]),
                              ("CMO", cmo, d["cmo"]["obj"]),
                              ("CMICT", cmict, d["cmict"]["obj"])):
            val = fn(d)
            dif = (val - obj) / obj if obj else 0
            fl = "OK" if abs(dif) <= 0.001 else "DIF"
            if fl != "OK":
                ok = False
            print(f"  {emp:7} {serv:14} {comp:6} = {val:10,.2f}  (obj {obj:10,.2f})  {fl}")
        # nota del hallazgo amb
        if emp == "AMB":
            limpio = cmict(d, con_doble_conteo=False)
            print(f"          └ CMICT sin el doble conteo de vehículos = {limpio:,.2f} "
                  f"(hallazgo CMICT!D33, $7.211.168)")
    print("\nTODO REPRODUCE" if ok else "\n*** DIFERENCIAS ***")
    return ok


if __name__ == "__main__":
    autoprueba()
