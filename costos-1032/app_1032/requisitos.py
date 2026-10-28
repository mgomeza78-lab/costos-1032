# -*- coding: utf-8 -*-
"""Matriz de requisitos de cargue por año tarifario (Res. CRA 1032/2026).

Define qué secciones del cargue aplican en cada período. La mayoría aplica en todos los períodos;
unas pocas son exclusivas del **período de inicio** (los insumos del régimen 688 que arman el BCR0),
y otras aparecen **desde el año tarifario 1** (el POIR 1032 y la ejecución de obras del año).

Claves de sección usadas en el riel y en la validación:
  · Gestión de información:  aps · comercial · agua · balance · costos · cmict   (todas: siempre)
  · Base de capital regulado:
        bcr_agua688  (Agua facturada 688 y segmento)     — SOLO inicio
        bcr0         (BCR de inicio)                       — SOLO inicio
        poir688_plan (POIR 688 · planeado)                — SOLO inicio
        poir688_ejec (POIR 688 · ejecutado)               — SOLO inicio
        activos      (Activos administrativos y operativos) — siempre
        provision    (Provisión POIR Res. 950)            — siempre
        poir1032_plan (POIR 1032 · plan de inversiones)   — DESDE año 1
        poir1032_ejec (Ejecución de obras del año)        — DESDE año 1
  · metas: en el inicio solo se identifican; se cuantifican/evalúan DESDE el año 1 (ver `metas_modo`).
"""

SOLO_INICIO = {"bcr_agua688", "bcr0", "poir688_plan", "poir688_ejec"}
DESDE_ANIO1 = {"poir1032_plan", "poir1032_ejec"}


def es_inicio(periodo_clave):
    return (periodo_clave or "inicio") == "inicio"


def aplica(periodo_clave, seccion):
    """¿La sección de cargue aplica en el período (clave 'inicio' / 'a1'…'a10')?"""
    if seccion in SOLO_INICIO:
        return es_inicio(periodo_clave)
    if seccion in DESDE_ANIO1:
        return not es_inicio(periodo_clave)
    return True


def metas_modo(periodo_clave):
    """'identificar' en el período de inicio (solo se enuncian), 'cuantificar' desde el año 1
    (el sistema evalúa cumplimiento con los parámetros que ingresa el usuario)."""
    return "identificar" if es_inicio(periodo_clave) else "cuantificar"
