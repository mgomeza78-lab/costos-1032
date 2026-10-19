# -*- coding: utf-8 -*-
"""Roles y matriz de permisos (control de acceso basado en roles).

El aislamiento por empresa lo garantiza la RLS en la base (db.py + 002_rls.sql);
aquí se controla QUÉ puede hacer cada rol (acciones), de forma complementaria.
"""

ROLES = {
    "admin":    "Administrador",
    "analista": "Analista",
    "empresa":  "Empresa",
    "auditor":  "Auditor (solo lectura)",
}

# acción -> roles autorizados
_MATRIZ = {
    "ver_resultados":       {"admin", "analista", "empresa", "auditor"},
    "cargar_mensual":       {"admin", "analista", "empresa"},
    "procesar_indexacion":  {"admin", "analista"},
    "administrar_ipc":      {"admin", "analista"},
    "recalcular":           {"admin", "analista"},
    "generar_entregables":  {"admin", "analista"},
    "editar_normativa":     {"admin"},
    "crear_empresa":        {"admin"},
    "administrar_usuarios": {"admin"},
    "ver_otras_empresas":   {"admin", "analista"},
    "ver_auditoria":        {"admin"},
}


def rol_nombre(codigo):
    return ROLES.get(codigo, codigo)


def can(user, accion):
    """True si el rol del usuario puede ejecutar la acción."""
    if not user:
        return False
    return user.get("rol") in _MATRIZ.get(accion, set())


def matriz():
    """La matriz como filas, para mostrarla en la UI."""
    acciones = list(_MATRIZ.keys())
    etiquetas = {
        "ver_resultados": "Ver resultados y tableros",
        "cargar_mensual": "Cargar datos mensuales de su empresa",
        "procesar_indexacion": "Correr la indexación mensual (gatillo 3%)",
        "administrar_ipc": "Cargar el índice IPC mensual",
        "recalcular": "Correr cálculo / recálculo",
        "generar_entregables": "Generar entregables (Word/Excel)",
        "editar_normativa": "Editar parámetros regulatorios",
        "crear_empresa": "Dar de alta empresas",
        "administrar_usuarios": "Administrar usuarios",
        "ver_otras_empresas": "Ver datos de otras empresas",
        "ver_auditoria": "Consultar la bitácora de auditoría",
    }
    filas = []
    for a in acciones:
        filas.append({
            "accion": etiquetas.get(a, a),
            "empresa": "empresa" in _MATRIZ[a],
            "auditor": "auditor" in _MATRIZ[a],
            "analista": "analista" in _MATRIZ[a],
            "admin": "admin" in _MATRIZ[a],
        })
    return filas
