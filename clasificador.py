# -*- coding: utf-8 -*-
"""Clasificador contable — Balance de Prueba → componentes de la Res. CRA 1032.

Aplica el **catálogo de clasificación por empresa** (cuenta PUC → subcomponente/componente),
extraído del Maestro de Codificación Contable, al balance ya normalizado (`lector_balance`).
Agrega los saldos por subcomponente (CAC-1..6, COC-1..5, CE, CIQ, ICTA…) y por componente
(CMA/CMO/CMI/CMICT/Excluido), y arma los numeradores CACe y COCe.

El catálogo es **editable y por empresa** (cada prestador tiene su propio plan de cuentas).
Las cuentas del balance que no estén en el catálogo se reportan como «sin clasificar» para que
el analista las agregue (no se pierden ni se cuentan mal).
"""
import csv
import io
from collections import defaultdict

COMPARABLES_COC = ("COC-1", "COC-2", "COC-3", "COC-4", "COC-5")


def cargar_catalogo(contenido):
    """CSV del catálogo -> dict codigo_norm -> (subcomponente, componente, traslado)."""
    cat = {}
    for r in csv.DictReader(io.StringIO(contenido)):
        cn = (r.get("codigo_norm") or "").strip()
        if not cn:
            continue
        cat[cn] = (r.get("subcomponente", "").strip(),
                   r.get("componente", "").strip(),
                   (r.get("traslado") or "").strip())
    return cat


def _hojas(balance_filas):
    """Códigos HOJA del balance: los que ningún otro código extiende (evita doble conteo
    de las cuentas agregadas del PUC: 5 → 51 → 5101 → 510101 → 51010101)."""
    codes = [f["codigo_norm"] for f in balance_filas if f.get("codigo_norm")]
    cset = set(codes)
    # ordenar por longitud para construir rápido el conjunto de 'tiene hijo'
    tiene_hijo = set()
    ordenados = sorted(cset, key=len)
    for c in cset:
        # un ancestro propio de c queda marcado como 'con hijo'
        for L in range(1, len(c)):
            pre = c[:L]
            if pre in cset:
                tiene_hijo.add(pre)
    return {c for c in cset if c not in tiene_hijo}


def clasificar(balance_filas, catalogo, valor="saldo_final"):
    """Clasifica el balance (de lector_balance) con el catálogo.

    Solo las cuentas HOJA se cuentan, y cada una se asigna por el **prefijo más largo** del
    catálogo (una cuenta del balance puede ser más detallada que la del catálogo). Devuelve
    (por_subcomponente, por_componente, sin_clasificar); sin_clasificar lista las cuentas hoja
    de gasto/costo (clase 5/7) no mapeadas, para que el analista las agregue al catálogo.
    """
    hojas = _hojas(balance_filas)
    cat_codes = sorted(catalogo.keys(), key=len, reverse=True)
    sub = defaultdict(float)
    comp = defaultdict(float)
    sin = []
    for f in balance_filas:
        cn = f.get("codigo_norm", "")
        if not cn or cn not in hojas:
            continue
        val = f.get(valor)
        if val is None:
            val = f.get("saldo_final") or f.get("debito") or 0.0
        if not val:
            continue
        key = cn if cn in catalogo else next((c for c in cat_codes if cn.startswith(c)), None)
        if key:
            sc, cp, _ = catalogo[key]
            sub[sc] += val
            comp[cp] += val
        elif cn[:1] in ("5", "7"):
            sin.append((cn, f.get("nombre"), val))
    return dict(sub), dict(comp), sin


def sugerir(codigo_norm, catalogo):
    """Sugiere el subcomponente para una cuenta nueva por el prefijo más largo del catálogo."""
    for c in sorted(catalogo.keys(), key=len, reverse=True):
        if codigo_norm.startswith(c) or c.startswith(codigo_norm):
            return catalogo[c][0], catalogo[c][1]
    return None, None


def numeradores(por_subcomponente):
    """CACe, COCe comparables, CE/CIQ/COIR contables, a partir de la agregación."""
    s = por_subcomponente
    cace = sum(v for k, v in s.items() if k.startswith("CAC-"))
    coce = sum(s.get(k, 0.0) for k in COMPARABLES_COC)
    return {
        "CACe": cace,
        "COCe_comparables": coce,
        "CE_contable": s.get("CE", 0.0),
        "CIQ_contable": s.get("CIQ", 0.0),
        "COIR": s.get("COIR", 0.0),
        "ICTA": s.get("ICTA", 0.0),
        "ICTO": s.get("ICTO", 0.0),
        "TA": s.get("TA", 0.0),
    }
