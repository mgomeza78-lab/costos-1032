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
import re
from collections import defaultdict

COMPARABLES_COC = ("COC-1", "COC-2", "COC-3", "COC-4", "COC-5")


def cargar_catalogo(contenido):
    """CSV del catálogo -> dict codigo_norm -> (subcomponente, componente, traslado, servicio).
    `servicio` ('acueducto'/'alcantarillado' o vacío) es la asignación por cuenta de la clase 7;
    vacío = la cuenta se reparte por el % de la clase 5. Tolera BOM y encabezados en
    mayúsculas/espacios; si falta 'codigo_norm' lo deriva de 'codigo'."""
    cat = {}
    for raw in csv.DictReader(io.StringIO((contenido or "").lstrip("﻿"))):
        r = {(k or "").strip().lstrip("﻿").lower(): (v or "") for k, v in raw.items()}
        cn = r.get("codigo_norm", "").strip() or re.sub(r"\D", "", r.get("codigo", ""))
        if not cn:
            continue
        cat[cn] = (r.get("subcomponente", "").strip(),
                   r.get("componente", "").strip(),
                   r.get("traslado", "").strip(),
                   (r.get("servicio", "").strip().lower() or ""))
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
            sc, cp, _tr, _sv = catalogo[key]
            sub[sc] += val
            comp[cp] += val
        elif cn[:1] in ("5", "7"):
            sin.append((cn, f.get("nombre"), val))
    return dict(sub), dict(comp), sin


def totales_clase(balance_filas, valor="saldo_final"):
    """Totales de control del balance por CLASE PUC, usando SOLO cuentas hoja (sin doble conteo
    de las cuentas agregadas: 5 → 51 → 5101 …): clase 5 (gastos/administración) y clase 7
    (costos/operación). Independiente del catálogo, para reconciliar lo cargado contra el balance
    de la empresa. Devuelve {'5','7','n5','n7'}."""
    hojas = _hojas(balance_filas)
    out = {"5": 0.0, "7": 0.0, "n5": 0, "n7": 0}
    for f in balance_filas:
        cn = f.get("codigo_norm", "")
        if not cn or cn not in hojas:
            continue
        val = f.get(valor)
        if val is None:
            val = f.get("saldo_final") or f.get("debito") or 0.0
        if not val:
            continue
        d = cn[:1]
        if d == "5":
            out["5"] += val
            out["n5"] += 1
        elif d == "7":
            out["7"] += val
            out["n7"] += 1
    return out


def sugerir(codigo_norm, catalogo):
    """Sugiere el subcomponente para una cuenta nueva por el prefijo más largo del catálogo."""
    for c in sorted(catalogo.keys(), key=len, reverse=True):
        if codigo_norm.startswith(c) or c.startswith(codigo_norm):
            return catalogo[c][0], catalogo[c][1]
    return None, None


def numeradores(por_subcomponente):
    """CACe, COCe comparables, CE/CIQ/COIR contables, a partir de la agregación.

    CACe = suma de los CAC reconocidos (CAC-1..6 y CAC-2.COM), es decir los de componente CMA;
    se EXCLUYE CAC-X ('Costos administrativos NO reconocidos', componente Excluido), igual que
    COCe excluye COC-X. Coincide con la definición validada de `nucleo.numerador_cac_coc.cace`
    (suma de subcomponentes con componente == 'CMA'); art. 2.1.2.1.3.2.4.
    """
    s = por_subcomponente
    cace = sum(v for k, v in s.items() if k.startswith("CAC-") and not k.endswith("-X"))
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


def clasificar_detalle(balance_filas, catalogo, valor="saldo_final"):
    """Clasifica el balance por (componente, subcomponente) en TRES cubetas, para que el reparto
    por servicio se pueda recomputar luego con cualquier %, Y devuelve el detalle por CUENTA:

      - `ac_dir`  : cuentas con servicio 'acueducto' en el catálogo (clase 7, cont. separada);
      - `al_dir`  : cuentas con servicio 'alcantarillado';
      - `repartir`: cuentas sin servicio (clase 5: CMA e impuestos admin.), que se reparten por %.

    Devuelve (buckets, cuentas, sin):
      · buckets = {(componente, subcomponente): {ac_dir, al_dir, repartir}}
      · cuentas = [{codigo, nombre, componente, subcomponente, ac_dir, al_dir, repartir}]  (saldo≠0)
      · sin     = cuentas hoja de clase 5/7 no mapeadas.
    """
    hojas = _hojas(balance_filas)
    cat_codes = sorted(catalogo.keys(), key=len, reverse=True)
    buckets = defaultdict(lambda: {"ac_dir": 0.0, "al_dir": 0.0, "repartir": 0.0})
    cuentas = []
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
        if not key:
            if cn[:1] in ("5", "7"):
                sin.append((cn, f.get("nombre"), val))
            continue
        sc, cp, _tr, serv = catalogo[key]
        # Clase 7 sin servicio en el catálogo: inferir por el código de la cuenta
        # (7503… = alcantarillado; 7501/7502/7504… = acueducto). Robustez si el catálogo
        # cargado aún no trae la columna 'servicio'.
        if not serv and cn[:1] == "7":
            if cn.startswith("7503"):
                serv = "alcantarillado"
            elif cn.startswith(("7501", "7502", "7504")):
                serv = "acueducto"
        ad = al = rp = 0.0
        if serv == "acueducto":
            ad = val
        elif serv == "alcantarillado":
            al = val
        else:
            rp = val
        b = buckets[(cp, sc)]
        b["ac_dir"] += ad
        b["al_dir"] += al
        b["repartir"] += rp
        cuentas.append({"codigo": cn, "nombre": f.get("nombre"), "componente": cp,
                        "subcomponente": sc, "ac_dir": ad, "al_dir": al, "repartir": rp})
    return {k: dict(v) for k, v in buckets.items()}, cuentas, sin


def clasificar_buckets(balance_filas, catalogo, valor="saldo_final"):
    """Cubetas por (componente, subcomponente). Ver `clasificar_detalle` para el detalle por cuenta."""
    buckets, _cuentas, sin = clasificar_detalle(balance_filas, catalogo, valor)
    return buckets, sin


def aplicar_pct(buckets, pct_ac=0.52):
    """Reparte las cubetas por servicio con `pct_ac`: devuelve {(componente, subcomponente, servicio): valor}.
    ac = ac_dir + repartir·pct_ac ; al = al_dir + repartir·(1−pct_ac)."""
    agg = {}
    for (cp, sc), b in buckets.items():
        ac = b.get("ac_dir", 0.0) + b.get("repartir", 0.0) * pct_ac
        al = b.get("al_dir", 0.0) + b.get("repartir", 0.0) * (1.0 - pct_ac)
        if ac:
            agg[(cp, sc, "acueducto")] = ac
        if al:
            agg[(cp, sc, "alcantarillado")] = al
    return agg


def clasificar_servicio(balance_filas, catalogo, pct_ac=0.52, valor="saldo_final"):
    """Compatibilidad: clasifica y reparte por servicio en un paso (buckets + pct)."""
    buckets, sin = clasificar_buckets(balance_filas, catalogo, valor)
    return aplicar_pct(buckets, pct_ac), sin


def numeradores_por_servicio(agg):
    """A partir de `clasificar_servicio`, arma los numeradores de costo POR SERVICIO:
    {servicio: {CACe, COCe_comparables, CE_contable, COIR, ICTA, ICTO, TA}}. Mismo criterio que
    `numeradores()` pero separado por servicio (para el reparto del balance en el motor)."""
    out = {}
    for (cp, sc, serv), v in agg.items():
        d = out.setdefault(serv, defaultdict(float))
        if sc.startswith("CAC-") and not sc.endswith("-X"):
            d["CACe"] += v
        if sc in COMPARABLES_COC:
            d["COCe_comparables"] += v
        if sc == "CE":
            d["CE_contable"] += v
        if sc == "COIR":
            d["COIR"] += v
        if sc in ("ICTA", "ICTO", "TA"):
            d[sc] += v
    return {s: dict(d) for s, d in out.items()}
