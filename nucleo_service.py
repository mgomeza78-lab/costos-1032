# -*- coding: utf-8 -*-
"""Puente entre la base multiempresa y el núcleo de cálculo ya validado.

El núcleo (perfiles_empresa, bcr0_cmi, numerador_cac_coc, componentes_cmx,
datos_empresa) vive en ./nucleo y reproduce al peso los costos económicos de
referencia de cada empresa. Aquí se resuelve una empresa (por su `codigo`) a su
perfil y se corre el cálculo, devolviendo filas listas para `resultado_componente`.
"""
import os
import sys

NUCLEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nucleo")
if NUCLEO_DIR not in sys.path:
    sys.path.insert(0, NUCLEO_DIR)

import perfiles_empresa as _pe   # noqa: E402
import datos_empresa as _de      # noqa: E402

PERFILES = _pe.PERFILES


def perfil_existe(codigo):
    return codigo in PERFILES


def codigos_disponibles():
    return sorted(PERFILES.keys())


def _val(dato):
    """Desenvuelve un Dato(valor=...) o devuelve el valor tal cual."""
    return getattr(dato, "valor", dato)


def perfil_resumen(codigo):
    """Atributos núcleo de una empresa, para dar de alta su registro."""
    p = PERFILES[codigo]
    servicios = [s.value for s in p.servicios]
    return {
        "codigo": p.id,
        "nombre": p.nombre,
        "municipio": p.municipio,
        "segmento": p.segmento,
        "esquema": p.esquema,
        "presta_ac": "acueducto" in servicios,
        "presta_al": "alcantarillado" in servicios,
        "r": _val(p.parametros.get("r")),
        "kct": _val(p.parametros.get("kct")),
        "fecha_inicio_688": p.fecha_inicio_688,
        "fecha_inicio_1032": p.fecha_inicio_1032,
        "aplicacion_1032_tardia": bool(p.aplicacion_1032_tardia),
    }


def calcular(codigo):
    """Corre el núcleo validado y devuelve las filas de resultado por componente."""
    p = PERFILES[codigo]
    R = _de.resultados(p)
    filas = []
    for servicio, comps in R["comp"].items():
        for comp, d in comps.items():
            filas.append({
                "servicio": servicio,
                "componente": comp,
                "valor": d.get("valor"),
                "unidad": d.get("unidad"),
                "procedencia": d.get("proc"),
                "fuente": d.get("fuente"),
                "articulo": _de.ART.get(comp, ""),
            })
    return filas
