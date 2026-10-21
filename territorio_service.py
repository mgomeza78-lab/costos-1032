# -*- coding: utf-8 -*-
"""Territorio (DIVIPOLA) y segmentación de la Res. CRA 1032 de 2026.

Segmentación (art. 2.1.2.1.1.6): se clasifica por el número de suscriptores al
31 de diciembre de 2024, sumando TODAS las APS y tomando el servicio con mayor
número de suscriptores. El prestador puede optar por un segmento superior
(decisión irreversible). Rangos:
  1: > 300.000 · 2: 90.001–300.000 · 3: 17.001–90.000 · 4: 5.001–17.000.

También expone el catálogo DIVIPOLA (departamentos y municipios) para el alta de
empresas y la carga del listado nacional desde el CSV oficial del DANE.
"""
import re
from sqlalchemy import text

# La metodología del subtítulo aplica a prestadores con > 5.000 suscriptores
# urbanos (art. 2.1.2.1.1.1).
MIN_AMBITO = 5000


def segmento_por_suscriptores(conn, n):
    """(segmento_id, nombre) según el número de suscriptores, o (None, motivo)."""
    if n is None:
        return None, "sin dato de suscriptores"
    if n <= MIN_AMBITO:
        return None, f"{n:,} ≤ 5.000 suscriptores: fuera del ámbito del subtítulo (verificar régimen)"
    row = conn.execute(text(
        "SELECT id, nombre FROM segmento "
        "WHERE CAST(:n AS integer) BETWEEN susc_min AND COALESCE(susc_max, 2147483647) "
        "ORDER BY id LIMIT 1"), {"n": int(n)}).mappings().first()
    return (row["id"], row["nombre"]) if row else (None, "sin segmento aplicable")


def segmentos(conn):
    return conn.execute(text(
        "SELECT id, nombre, susc_min, susc_max FROM segmento ORDER BY id")).mappings().all()


def departamentos(conn):
    return conn.execute(text(
        "SELECT cod_dane, nombre FROM departamento ORDER BY nombre")).mappings().all()


def municipios(conn):
    return conn.execute(text(
        "SELECT m.cod_dane, m.cod_dpto, m.nombre, d.nombre AS departamento "
        "FROM municipio m JOIN departamento d ON d.cod_dane = m.cod_dpto "
        "ORDER BY d.nombre, m.nombre")).mappings().all()


def municipios_de_empresa(conn, empresa_id):
    return conn.execute(text(
        "SELECT m.cod_dane, m.nombre, d.nombre AS departamento "
        "FROM empresa_municipio em JOIN municipio m ON m.cod_dane = em.cod_dane "
        "JOIN departamento d ON d.cod_dane = m.cod_dpto "
        "WHERE em.empresa_id = :e ORDER BY d.nombre, m.nombre"),
        {"e": empresa_id}).mappings().all()


def set_municipios(conn, empresa_id, codigos):
    """Reemplaza los municipios atendidos por la empresa. Devuelve cuántos quedaron."""
    conn.execute(text("DELETE FROM empresa_municipio WHERE empresa_id=:e"), {"e": empresa_id})
    n = 0
    for cod in codigos or []:
        cod = (cod or "").strip()
        if re.fullmatch(r"\d{5}", cod):
            conn.execute(text("INSERT INTO empresa_municipio(empresa_id,cod_dane) VALUES (:e,:c) "
                              "ON CONFLICT DO NOTHING"), {"e": empresa_id, "c": cod})
            n += 1
    return n


# El catálogo DIVIPOLA (departamentos y municipios) es una tabla fija del sistema:
# se carga desde la base con las migraciones 010 y 011; no se sube por la aplicación.
