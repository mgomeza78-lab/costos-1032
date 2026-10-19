# -*- coding: utf-8 -*-
"""Ensamblador de resultados por empresa — fuente única para los generadores F4.

Toma el perfil (perfiles_empresa) y los numeradores de componentes (componentes_cmx)
y arma una estructura uniforme que consumen el generador de memorias (Excel) y el
de documento soporte (Word). No calcula nada nuevo: ordena lo ya validado.
"""
from perfiles_empresa import PERFILES

try:
    from componentes_cmx import COMPONENTES as _CMX
except Exception:
    _CMX = {}

ART = {  # artículo de la Res. 1032 por componente
    "CMA": "2.1.2.1.3.2.1.", "CMO": "2.1.2.1.3.4.1.", "CMI": "2.1.2.1.3.5.1.",
    "CMICT": "2.1.2.1.3.6.1.", "BCR0": "2.1.2.1.3.5.4.",
    "CARGO_FIJO": "2.1.2.1.2.1.", "CARGO_CONSUMO": "2.1.2.1.2.1.",
}
ORDEN_COMP = ["CMA", "CMO", "CMI", "CMICT", "CARGO_FIJO", "CARGO_CONSUMO", "BCR0"]


def resultados(perfil):
    R = {"id": perfil.id, "nombre": perfil.nombre, "municipio": perfil.municipio,
         "segmento": perfil.segmento, "servicios": [s.value for s in perfil.servicios],
         "esquema": perfil.esquema, "params": perfil.parametros, "fechas": perfil.fechas,
         "selectores": perfil.selectores, "fuentes_datos": perfil.fuentes_datos,
         "notas": perfil.notas, "numerador": perfil.numerador or {},
         "fecha_688": perfil.fecha_inicio_688, "fecha_1032": perfil.fecha_inicio_1032,
         "tardia": perfil.aplicacion_1032_tardia, "comp": {}}
    for o in perfil.objetivos:
        s = o.servicio.value if o.servicio else "—"
        R["comp"].setdefault(s, {})[o.componente] = {
            "valor": o.valor, "unidad": o.unidad, "proc": o.proc.value, "fuente": o.fuente}
    for s, d in R["comp"].items():
        if "CMA" in d:
            d["CARGO_FIJO"] = {"valor": d["CMA"]["valor"], "unidad": "$/susc·mes",
                               "proc": d["CMA"]["proc"], "fuente": "= CMA"}
        cc = sum(d[k]["valor"] for k in ("CMO", "CMI", "CMICT") if k in d)
        if cc:
            d["CARGO_CONSUMO"] = {"valor": cc, "unidad": "$/m³", "proc": "calculada",
                                  "fuente": "= CMO + CMI + CMICT"}
    return R


def numeradores(emp, serv):
    """Detalle del numerador de CMA/CMO/CMICT (si está disponible en componentes_cmx)."""
    return _CMX.get((emp, serv))


def todas():
    return {k: resultados(p) for k, p in PERFILES.items()}


if __name__ == "__main__":
    for k, R in todas().items():
        serv = ", ".join(R["servicios"])
        print(f"{k:12} seg {R['segmento']} | {serv} | componentes en {list(R['comp'])}")
