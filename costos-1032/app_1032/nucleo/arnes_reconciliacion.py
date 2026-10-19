# -*- coding: utf-8 -*-
"""Arnés de reconciliación — capa común de la consolidación Res. CRA 1032.

Dado el perfil de una empresa (con sus objetivos = cifras aceptadas) y un
diccionario de CANDIDATOS (las cifras que produce el núcleo de cálculo o el
adaptador del workbook), verifica que cada objetivo se reproduzca dentro de la
tolerancia y arma un reporte. Una diferencia NO se silencia: se reporta.

Estados:
  · PASA       — hay candidato y la diferencia está dentro de tolerancia.
  · FALLA      — hay candidato y la diferencia excede la tolerancia.
  · PENDIENTE  — todavía no hay candidato (el núcleo aún no reproduce ese objetivo).

Los candidatos se indexan por (servicio, componente); servicio es un valor del
enum Servicio o None para cifras transversales (factura conjunta, COC).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

from perfiles_empresa import PerfilEmpresa, Objetivo, Servicio

PASA, FALLA, PENDIENTE = "PASA", "FALLA", "PENDIENTE"


@dataclass
class Resultado:
    empresa: str
    segmento: int
    servicio: str          # "acueducto" / "alcantarillado" / "—"
    componente: str
    unidad: str
    objetivo: float
    procedencia: str
    fuente: str
    candidato: Optional[float]
    dif_abs: Optional[float]
    dif_rel: Optional[float]
    estado: str


def _clave(servicio: Optional[Servicio], componente: str) -> Tuple[str, str]:
    return (servicio.value if servicio else "—", componente)


def reconciliar(perfil: PerfilEmpresa,
                candidatos: Optional[Dict[Tuple[str, str], float]] = None) -> List[Resultado]:
    """Reconcilia los objetivos del perfil contra los candidatos entregados.

    candidatos: dict {(servicio_str, componente) -> valor}. Si es None o no trae
    la clave de un objetivo, ese objetivo queda PENDIENTE.
    """
    candidatos = candidatos or {}
    salida: List[Resultado] = []
    for obj in perfil.objetivos:
        serv_str, comp = _clave(obj.servicio, obj.componente)
        cand = candidatos.get((serv_str, comp))
        if cand is None:
            estado, dif_abs, dif_rel = PENDIENTE, None, None
        else:
            dif_abs = cand - obj.valor
            dif_rel = (dif_abs / obj.valor) if obj.valor else None
            dentro = abs(dif_abs) <= obj.tol_abs or (
                obj.valor != 0 and abs(dif_rel) <= obj.tol_rel)
            estado = PASA if dentro else FALLA
        salida.append(Resultado(
            empresa=perfil.id, segmento=perfil.segmento, servicio=serv_str,
            componente=comp, unidad=obj.unidad, objetivo=obj.valor,
            procedencia=obj.proc.value, fuente=obj.fuente, candidato=cand,
            dif_abs=dif_abs, dif_rel=dif_rel, estado=estado))
    return salida


def resumen(resultados: List[Resultado]) -> Dict[str, int]:
    r = {PASA: 0, FALLA: 0, PENDIENTE: 0}
    for x in resultados:
        r[x.estado] += 1
    return r


def tablero(perfiles: List[PerfilEmpresa],
            candidatos_por_empresa: Optional[Dict[str, Dict[Tuple[str, str], float]]] = None
            ) -> List[Resultado]:
    """Arma el tablero completo (todas las empresas, todos los objetivos)."""
    candidatos_por_empresa = candidatos_por_empresa or {}
    out: List[Resultado] = []
    for p in perfiles:
        out.extend(reconciliar(p, candidatos_por_empresa.get(p.id)))
    return out


if __name__ == "__main__":
    from perfiles_empresa import cargar_perfiles
    res = tablero(cargar_perfiles())
    print(f"{len(res)} objetivos en el tablero")
    for k, v in resumen(res).items():
        print(f"  {k}: {v}")
