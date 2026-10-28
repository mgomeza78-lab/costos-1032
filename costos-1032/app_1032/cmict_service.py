# -*- coding: utf-8 -*-
"""CMICT al detalle — Impuestos, Contribuciones y Tasas (art. 2.1.2.1.3.6, Res. CRA 1032).

CICT = ICTA + ICTO + TA   →   CMICT = CICT × (1 + kct) × Fa_cmict / CCP   (art. 2.1.2.1.3.6.1)

  · ICTA (art. .6.3): 15 conceptos taxativos (a–o). Solo lo EFECTIVAMENTE PAGADO y reconocible;
       lo que no está en la lista no entra a tarifa aunque se haya pagado.
  · ICTO (art. .6.4): 8 conceptos taxativos (a–h). Igual criterio.
  · TA — Tasas ambientales:
       · TUA  (acueducto, art. .6.5): valor efectivamente pagado por uso del agua (par. 4).
       · Tasa retributiva (alcantarillado, art. .6.6): se reconoce a Frec = 1. El mayor valor
         por FR>1 (incumplimiento de metas) NO es trasladable (Dcto 1076/2015, par. 2 art. 2.2.9.7.4.4).

Solo se calcula; las ENTRADAS las aporta la empresa. El valor del balance se muestra como
referencia contable para conciliar (los numeradores del balance son el respaldo por defecto del
ICTA/ICTO; la TA se reconoce del detalle de tasas, no del balance).
"""
import csv
import io
from sqlalchemy import text

FREC = 1.0  # Factor regional reconocido en tarifa (CRA 1032): por ahora solo traslado a Frec = 1.

# Catálogo taxativo. (llave, letra, nombre, articulo)
ICTA_ITEMS = [
    ("3.a-1",  "a", "Cuotas de fiscalización y auditaje (SSPD)",            "2.1.2.1.3.6.3.a"),
    ("3.a-2",  "b", "Contribuciones a la SSPD y a la CRA",                  "2.1.2.1.3.6.3.b"),
    ("3.a-3",  "c", "Gravamen a los movimientos financieros (administrativo)", "2.1.2.1.3.6.3.c"),
    ("3.a-4",  "d", "IVA de compras administrativas afectas al servicio",   "2.1.2.1.3.6.3.d"),
    ("3.a-5",  "e", "Impuesto al consumo de compras administrativas",       "2.1.2.1.3.6.3.e"),
    ("3.a-6",  "f", "Impuesto de alumbrado público",                        "2.1.2.1.3.6.3.f"),
    ("3.a-7",  "g", "Impuesto de avisos y tableros",                        "2.1.2.1.3.6.3.g"),
    ("3.a-8",  "h", "Impuesto de industria y comercio (ICA)",               "2.1.2.1.3.6.3.h"),
    ("3.a-9",  "i", "Publicidad exterior visual (cambio de comportamiento del usuario)", "2.1.2.1.3.6.3.i"),
    ("3.a-10", "j", "Impuesto predial unificado — inmuebles administrativos", "2.1.2.1.3.6.3.j"),
    ("3.a-11", "k", "Peajes administrativos",                               "2.1.2.1.3.6.3.k"),
    ("3.a-12", "l", "Impuesto de registro",                                 "2.1.2.1.3.6.3.l"),
    ("3.a-13", "m", "Sobretasa a la gasolina — vehículos administrativos",  "2.1.2.1.3.6.3.m"),
    ("3.a-14", "n", "Impuesto de timbre (administrativo)",                  "2.1.2.1.3.6.3.n"),
    ("3.a-15", "o", "Contribución por valorización — inmuebles administrativos", "2.1.2.1.3.6.3.o"),
]
ICTO_ITEMS = [
    ("4.a-1", "a", "Gravamen a los movimientos financieros (operativo)",   "2.1.2.1.3.6.4.a"),
    ("4.a-2", "b", "IVA de compras operativas afectas al servicio",        "2.1.2.1.3.6.4.b"),
    ("4.a-3", "c", "Impuesto al consumo de compras operativas",            "2.1.2.1.3.6.4.c"),
    ("4.a-4", "d", "Impuesto predial — bienes operativos afectos al servicio", "2.1.2.1.3.6.4.d"),
    ("4.a-5", "e", "Peajes operativos afectos al servicio",                "2.1.2.1.3.6.4.e"),
    ("4.a-6", "f", "Sobretasa a la gasolina — vehículos operativos",       "2.1.2.1.3.6.4.f"),
    ("4.a-7", "g", "Impuesto de timbre (operativo)",                       "2.1.2.1.3.6.4.g"),
    ("4.a-8", "h", "Contribución por valorización — bienes operativos",    "2.1.2.1.3.6.4.h"),
]
ITEMS = {"ICTA": ICTA_ITEMS, "ICTO": ICTO_ITEMS}
ITEM_NOMBRE = {it[0]: it[2] for lst in ITEMS.values() for it in lst}
ITEM_ART = {it[0]: it[3] for lst in ITEMS.values() for it in lst}
EXCLUIDOS = ("renta, ganancia ocasional, dividendos, patrimonio, impuesto al carbono, plusvalía, "
             "intereses de mora, sanciones y multas (art. 2.1.2.1.3.6.3/.4, par. 1–3)")


def _num(x):
    try:
        return float(x) if x is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# -------------------------------------------------------------------- cálculo retributiva
def calc_retributiva(r):
    """Total a Frec=1 (trasladable), total c/FR (pagado) y no recuperable, de un punto.
      base (Frec=1) = Tm_dbo·DBO + Tm_sst·SST     ;     total c/FR = base · Fr_liquidado
    Si el usuario aporta total_cfr, se respeta; si no, se estima con el Fr liquidado."""
    base = _num(r.get("tm_dbo")) * _num(r.get("carga_dbo")) + _num(r.get("tm_sst")) * _num(r.get("carga_sst"))
    total_fr1 = base * FREC
    fr = _num(r.get("fr_liquidado")) or 1.0
    total_cfr = _num(r.get("total_cfr")) or (base * fr)
    return {"base": base, "total_fr1": total_fr1, "total_cfr": total_cfr,
            "no_recuperable": max(total_cfr - total_fr1, 0.0)}


# -------------------------------------------------------------------- lectura
def tributo_lista(conn, empresa_id, anio, componente):
    """Conceptos del catálogo (ICTA/ICTO) con lo cargado (incluye + valor) por servicio."""
    rows = {}
    for r in conn.execute(text(
        "SELECT id, servicio, item, incluye, valor_pagado, observacion FROM cmict_tributo "
        "WHERE empresa_id=:e AND anio=:a AND componente=:c"),
            {"e": empresa_id, "a": anio, "c": componente}).mappings().all():
        rows.setdefault(r["item"], {})[r["servicio"]] = dict(r)
    out = []
    for llave, letra, nombre, art in ITEMS[componente]:
        out.append({"item": llave, "letra": letra, "nombre": nombre, "articulo": art,
                    "ac": rows.get(llave, {}).get("acueducto"),
                    "al": rows.get(llave, {}).get("alcantarillado")})
    return out


def tua_lista(conn, empresa_id, anio=None):
    sql = ("SELECT * FROM tasa_tua WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    sql += " ORDER BY anio DESC, trimestre, predio"
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]


def retributiva_lista(conn, empresa_id, anio=None):
    sql = "SELECT * FROM tasa_retributiva WHERE empresa_id=:e"
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    sql += " ORDER BY anio DESC, punto"
    out = []
    for r in conn.execute(text(sql), p).mappings().all():
        d = dict(r)
        d["calc"] = calc_retributiva(d)
        out.append(d)
    return out


# -------------------------------------------------------------------- totales → numeradores
def _pct_ac(conn, empresa_id):
    import ingesta
    return ingesta.get_pct_ac(conn, empresa_id)


def cuentas_componente(conn, empresa_id, anio, componente):
    """Cuentas del balance clasificadas a ICTA/ICTO (numerador_cuenta) con su valor CONTABLE por
    servicio y el AJUSTE (override) cargado. Es la base de la tabla por concepto: cada cuenta trae su
    valor contable y, si se diligencia, un valor distinto (p. ej. impuesto parcialmente excluido)."""
    pct = _pct_ac(conn, empresa_id)
    ov = {}
    for r in conn.execute(text(
        "SELECT servicio, item, incluye, valor_pagado FROM cmict_tributo "
        "WHERE empresa_id=:e AND anio=:a AND componente=:c"),
            {"e": empresa_id, "a": anio, "c": componente}).mappings():
        ov.setdefault(r["item"], {})[r["servicio"]] = dict(r)
    out = []
    for r in conn.execute(text(
        "SELECT codigo, nombre, ac_dir, al_dir, repartir FROM numerador_cuenta "
        "WHERE empresa_id=:e AND anio=:a AND cod_dane='' AND componente='CMICT' AND subcomponente=:c "
        "ORDER BY codigo"), {"e": empresa_id, "a": anio, "c": componente}).mappings():
        cod = r["codigo"]
        out.append({"codigo": cod, "nombre": r["nombre"],
                    "contable_ac": (r["ac_dir"] or 0.0) + (r["repartir"] or 0.0) * pct,
                    "contable_al": (r["al_dir"] or 0.0) + (r["repartir"] or 0.0) * (1.0 - pct),
                    "ac": ov.get(cod, {}).get("acueducto"), "al": ov.get(cod, {}).get("alcantarillado")})
    return out


def excluidos(conn, empresa_id, anio):
    """Impuestos/contribuciones NO reconocidos (subcomponente 'ICT-X') con su valor contable por
    servicio — la lista taxativa del parágrafo (renta, ganancia ocasional, patrimonio, impuesto al
    carbono, plusvalía, intereses de mora, sanciones y multas; art. 2.1.2.1.3.6.3/.4, par. 1–3)."""
    pct = _pct_ac(conn, empresa_id)
    out = []
    for r in conn.execute(text(
        "SELECT codigo, nombre, ac_dir, al_dir, repartir FROM numerador_cuenta "
        "WHERE empresa_id=:e AND anio=:a AND cod_dane='' AND subcomponente='ICT-X' "
        "ORDER BY (ac_dir+al_dir+repartir) DESC, codigo"), {"e": empresa_id, "a": anio}).mappings():
        out.append({"codigo": r["codigo"], "nombre": r["nombre"],
                    "ac": (r["ac_dir"] or 0.0) + (r["repartir"] or 0.0) * pct,
                    "al": (r["al_dir"] or 0.0) + (r["repartir"] or 0.0) * (1.0 - pct)})
    return out


def _recon(contable, ovr):
    """Valor reconocido de una cuenta en un servicio: el override si existe y se incluye; si no, el contable."""
    if ovr is None:
        return contable
    if not ovr.get("incluye"):
        return 0.0
    v = ovr.get("valor_pagado")
    return float(v) if v is not None else contable


def _comp_total(conn, empresa_id, anio, componente, servicio):
    rows = cuentas_componente(conn, empresa_id, anio, componente)
    if not rows:
        return None
    k = "ac" if (servicio or "").lower().startswith("acu") else "al"
    kc = "contable_ac" if k == "ac" else "contable_al"
    return sum(_recon(r[kc], r[k]) for r in rows)


def override_borrar(conn, empresa_id, anio, componente, servicio, codigo):
    conn.execute(text("DELETE FROM cmict_tributo WHERE empresa_id=:e AND anio=:a AND componente=:c "
                      "AND servicio=:s AND item=:i"),
                 {"e": empresa_id, "a": anio, "c": componente, "s": servicio, "i": codigo})


def ajuste_campo(componente, codigo, k):
    """Nombre del campo del formulario para el ajuste de una cuenta (componente, código, ac/al)."""
    return f"aj_{componente}_{codigo}_{k}"


def ajustes_guardar(conn, empresa_id, anio, getval, cargado_por=None):
    """Procesa la tabla de ajustes de ICTA/ICTO. Para cada cuenta y servicio: si el usuario
    diligenció un valor distinto, se guarda como ajuste (sustituye al contable); si lo dejó en
    blanco, se borra cualquier ajuste previo (vuelve al contable). Devuelve (n_guardados, n_borrados)."""
    guard = borr = 0
    for comp in ("ICTA", "ICTO"):
        for r in cuentas_componente(conn, empresa_id, anio, comp):
            cod = r["codigo"]
            for serv, k in (("acueducto", "ac"), ("alcantarillado", "al")):
                raw = getval(ajuste_campo(comp, cod, k))
                val = _pnum(raw)
                if raw is not None and str(raw).strip() != "" and val is not None:
                    tributo_guardar(conn, empresa_id, anio, comp, serv, cod, True, val,
                                    obs=r["nombre"], origen="ajuste", cargado_por=cargado_por)
                    guard += 1
                else:
                    override_borrar(conn, empresa_id, anio, comp, serv, cod)
                    borr += 1
    return guard, borr


def ta_de(conn, empresa_id, servicio, anio):
    """TA reconocida del servicio: TUA (acueducto, Σ pagado confirmado) o retributiva
    (alcantarillado, Σ total a Frec=1). None si no hay detalle de tasas cargado."""
    s = (servicio or "").lower()
    if s.startswith("acu"):
        n = conn.execute(text("SELECT count(*) FROM tasa_tua WHERE empresa_id=:e AND anio=:a AND servicio=:s"),
                         {"e": empresa_id, "a": anio, "s": s}).scalar()
        if not n:
            return None
        v = conn.execute(text(
            "SELECT COALESCE(SUM(valor),0) FROM tasa_tua WHERE empresa_id=:e AND anio=:a AND servicio=:s "
            "AND estado='pagado'"), {"e": empresa_id, "a": anio, "s": s}).scalar()
        return float(v or 0.0)
    rows = retributiva_lista(conn, empresa_id, anio=anio)
    rows = [r for r in rows if (r["servicio"] or "").lower().startswith("alcan")]
    return sum(r["calc"]["total_fr1"] for r in rows) if rows else None


def cmict_de(conn, empresa_id, servicio, anio):
    """(ICTA, ICTO, TA) reconocidos del módulo para el servicio/año. ICTA/ICTO = Σ del valor
    reconocido por cuenta (contable, salvo que haya un ajuste cargado por cuenta); None si el
    balance no está clasificado (para que el motor use el respaldo). TA siempre del módulo de tasas."""
    return (_comp_total(conn, empresa_id, anio, "ICTA", servicio),
            _comp_total(conn, empresa_id, anio, "ICTO", servicio),
            ta_de(conn, empresa_id, servicio, anio))


# -------------------------------------------------------------------- cargue (manual + masivo)
def _pnum(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    if "," in s:                 # coma decimal (formato CO): quita puntos de miles
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:       # varios puntos sin coma → separadores de miles
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _pint(s):
    v = _pnum(s)
    return int(v) if v is not None else None


def _leer_csv(texto):
    sample = (texto or "")[:3000]
    sep = ";" if sample.count(";") > sample.count(",") else ","
    rdr = csv.DictReader(io.StringIO((texto or "").lstrip("﻿")), delimiter=sep)
    return [{(k or "").strip().lower(): (v or "") for k, v in row.items()} for row in rdr]


def _serv(s):
    s = (s or "").strip().lower()
    return "alcantarillado" if s.startswith("alcan") else ("acueducto" if s.startswith("acu") else s)


def _si(s):
    return str(s or "").strip().lower() not in ("no", "n", "false", "0", "excluir", "no se incluye")


def tributo_guardar(conn, empresa_id, anio, componente, servicio, item, incluye, valor, obs=None,
                    origen="empresa", cargado_por=None):
    # `item` es el CÓDIGO de la cuenta del balance clasificada a ICTA/ICTO (el ajuste se guarda
    # por cuenta). Solo se valida el componente; el valor es el que sustituye al contable.
    if componente not in ITEMS or not str(item or "").strip():
        return None, "concepto inválido"
    conn.execute(text(
        "INSERT INTO cmict_tributo(empresa_id,anio,servicio,componente,item,incluye,valor_pagado,"
        " observacion,origen,cargado_por) VALUES (:e,:a,:s,:c,:it,:inc,:v,:ob,:og,:u) "
        "ON CONFLICT (empresa_id,anio,servicio,componente,item) DO UPDATE SET incluye=excluded.incluye, "
        "valor_pagado=excluded.valor_pagado, observacion=excluded.observacion, origen=excluded.origen, "
        "cargado_por=excluded.cargado_por, cargado_en=now()"),
        {"e": empresa_id, "a": int(anio), "s": _serv(servicio), "c": componente, "it": item,
         "inc": bool(incluye), "v": _pnum(valor) if not isinstance(valor, (int, float)) else valor,
         "ob": (obs or None), "og": origen, "u": cargado_por})
    return True, None


def tua_guardar(conn, empresa_id, anio, d, origen="empresa", cargado_por=None):
    if not (d.get("predio") or d.get("n_factura") or d.get("periodo") or d.get("trimestre")):
        return None, "identifique la factura (predio / n_factura / período)"
    conn.execute(text(
        "INSERT INTO tasa_tua(empresa_id,anio,servicio,trimestre,periodo,predio,codigo_predio,concesion,"
        " fuente,n_factura,uso,caudal_lts,tarifa_unit,factor_turno,factor_op,valor,resolucion_pago,"
        " fecha_pago,estado,observacion,origen,cargado_por) VALUES "
        "(:e,:a,'acueducto',:tr,:pe,:pr,:cp,:co,:fu,:nf,:us,:ca,:ta,:ft,:fo,:va,:rp,:fp,:es,:ob,:og,:u)"),
        {"e": empresa_id, "a": int(anio), "tr": (d.get("trimestre") or "").strip() or None,
         "pe": (d.get("periodo") or "").strip() or None, "pr": (d.get("predio") or "").strip() or None,
         "cp": (d.get("codigo_predio") or "").strip() or None, "co": (d.get("concesion") or "").strip() or None,
         "fu": (d.get("fuente") or "").strip() or None, "nf": (d.get("n_factura") or "").strip() or None,
         "us": (d.get("uso") or "").strip() or None, "ca": _pnum(d.get("caudal_lts")),
         "ta": _pnum(d.get("tarifa_unit")), "ft": _pnum(d.get("factor_turno")), "fo": _pnum(d.get("factor_op")),
         "va": _pnum(d.get("valor")), "rp": (d.get("resolucion_pago") or "").strip() or None,
         "fp": (d.get("fecha_pago") or "").strip() or None,
         "es": "pendiente" if str(d.get("estado") or "").strip().lower().startswith("pend") else "pagado",
         "ob": (d.get("observacion") or "").strip() or None, "og": origen, "u": cargado_por})
    return True, None


def retributiva_guardar(conn, empresa_id, anio, d, origen="empresa", cargado_por=None):
    punto = (d.get("punto") or "").strip()
    if not punto:
        return None, "el punto de vertimiento es obligatorio"
    conn.execute(text(
        "INSERT INTO tasa_retributiva(empresa_id,anio,servicio,punto,carga_dbo,carga_sst,tm_dbo,tm_sst,"
        " fr_liquidado,total_cfr,observacion,origen,cargado_por) VALUES "
        "(:e,:a,'alcantarillado',:p,:cd,:cs,:td,:ts,:fr,:tc,:ob,:og,:u) "
        "ON CONFLICT (empresa_id,anio,servicio,punto) DO UPDATE SET carga_dbo=excluded.carga_dbo, "
        "carga_sst=excluded.carga_sst, tm_dbo=excluded.tm_dbo, tm_sst=excluded.tm_sst, "
        "fr_liquidado=excluded.fr_liquidado, total_cfr=excluded.total_cfr, observacion=excluded.observacion, "
        "origen=excluded.origen, cargado_por=excluded.cargado_por, cargado_en=now()"),
        {"e": empresa_id, "a": int(anio), "p": punto, "cd": _pnum(d.get("carga_dbo")),
         "cs": _pnum(d.get("carga_sst")), "td": _pnum(d.get("tm_dbo")), "ts": _pnum(d.get("tm_sst")),
         "fr": _pnum(d.get("fr_liquidado")), "tc": _pnum(d.get("total_cfr")),
         "ob": (d.get("observacion") or "").strip() or None, "og": origen, "u": cargado_por})
    return True, None


def tributo_masivo(conn, empresa_id, anio, componente, texto, cargado_por=None):
    """CSV: item,servicio,incluye,valor_pagado,observacion. Reemplaza el componente del año."""
    filas = _leer_csv(texto)
    conn.execute(text("DELETE FROM cmict_tributo WHERE empresa_id=:e AND anio=:a AND componente=:c"),
                 {"e": empresa_id, "a": int(anio), "c": componente})
    n, err = 0, []
    for i, r in enumerate(filas, start=2):
        item = (r.get("item") or r.get("llave") or "").strip()
        if not item:
            continue
        ok, e = tributo_guardar(conn, empresa_id, anio, componente, r.get("servicio"), item,
                                _si(r.get("incluye")), r.get("valor_pagado") or r.get("valor"),
                                (r.get("observacion") or "").strip() or None, "masivo", cargado_por)
        if ok:
            n += 1
        else:
            err.append(f"fila {i}: {e}")
    return n, err


def tua_masivo(conn, empresa_id, anio, texto, cargado_por=None):
    """Toma el año de la columna `anio` de cada fila (si falta, el del selector) y reemplaza cada año presente."""
    filas = _leer_csv(texto)
    anios = {(_pint(r.get("anio")) or int(anio)) for r in filas if any((r.get(c) or "").strip() for c in TUA_HDR)}
    for a in anios:
        conn.execute(text("DELETE FROM tasa_tua WHERE empresa_id=:e AND anio=:a"), {"e": empresa_id, "a": a})
    n, err = 0, []
    for i, r in enumerate(filas, start=2):
        a = _pint(r.get("anio")) or int(anio)
        ok, e = tua_guardar(conn, empresa_id, a, r, "masivo", cargado_por)
        if ok:
            n += 1
        elif any((r.get(c) or "").strip() for c in TUA_HDR):
            err.append(f"fila {i}: {e}")
    return n, err


def retributiva_masivo(conn, empresa_id, anio, texto, cargado_por=None):
    """Toma el año de la columna `anio` de cada fila (si falta, el del selector) y reemplaza cada año presente."""
    filas = _leer_csv(texto)
    anios = {(_pint(r.get("anio")) or int(anio)) for r in filas if (r.get("punto") or "").strip()}
    for a in anios:
        conn.execute(text("DELETE FROM tasa_retributiva WHERE empresa_id=:e AND anio=:a"), {"e": empresa_id, "a": a})
    n, err = 0, []
    for i, r in enumerate(filas, start=2):
        a = _pint(r.get("anio")) or int(anio)
        ok, e = retributiva_guardar(conn, empresa_id, a, r, "masivo", cargado_por)
        if ok:
            n += 1
        elif (r.get("punto") or "").strip():
            err.append(f"fila {i}: {e}")
    return n, err


def eliminar(conn, empresa_id, tabla, rid):
    if tabla not in ("cmict_tributo", "tasa_tua", "tasa_retributiva", "tasa_soporte"):
        return
    conn.execute(text(f"DELETE FROM {tabla} WHERE empresa_id=:e AND id=:i"), {"e": empresa_id, "i": int(rid)})


# -------------------------------------------------------------------- soportes
def soporte_guardar(conn, empresa_id, anio, tipo, referencia, nombre, tipo_archivo, contenido, subido_por=None):
    conn.execute(text(
        "INSERT INTO tasa_soporte(empresa_id,anio,tipo,referencia,nombre,tipo_archivo,tamano,contenido,subido_por) "
        "VALUES (:e,:a,:t,:r,:n,:ta,:tm,:c,:u)"),
        {"e": empresa_id, "a": int(anio) if anio else None, "t": tipo, "r": (referencia or None),
         "n": nombre, "ta": tipo_archivo, "tm": len(contenido), "c": contenido, "u": subido_por})


def soporte_lista(conn, empresa_id, anio=None):
    sql = "SELECT id, anio, tipo, referencia, nombre, tipo_archivo, tamano, subido_en FROM tasa_soporte WHERE empresa_id=:e"
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    sql += " ORDER BY subido_en DESC"
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]


# -------------------------------------------------------------------- plantillas
# Tasas: año base i-1 (2025). El `anio` va como primera columna para que el archivo quede autodescrito.
TUA_HDR = ["anio", "trimestre", "periodo", "predio", "codigo_predio", "concesion", "fuente", "n_factura",
           "uso", "caudal_lts", "tarifa_unit", "factor_turno", "factor_op", "valor",
           "resolucion_pago", "fecha_pago", "estado"]
RETRIB_HDR = ["anio", "punto", "carga_dbo", "carga_sst", "tm_dbo", "tm_sst", "fr_liquidado", "total_cfr"]


def plantilla_tributo(componente):
    ej = [f"{it[0]},acueducto,si,0,{it[2]}" for it in ITEMS[componente][:3]]
    return (f"plantilla_{componente.lower()}.csv",
            "item,servicio,incluye,valor_pagado,observacion\n" + "\n".join(ej) + "\n")


def plantilla_tua():
    ej = ["2025,I-2025,Ene-Mar 2025,EL ACUEDUCTO,101600000119,0000006827,Río Las Ceibas,2025021267,Doméstico,"
          "800,10139,1,1,24333600,Res. 338 (25/07/2025),21/08/2025,pagado"]
    return "plantilla_tua.csv", ",".join(TUA_HDR) + "\n" + "\n".join(ej) + "\n"


def plantilla_retributiva():
    ej = ["2025,Acrópolis,13452.69,5780.30,215.84,92.29,2.15,7389748.87",
          "2025,San Silvestre,8875.32,1716.99,215.84,92.29,1.43,2965977.41"]
    return "plantilla_tasa_retributiva.csv", ",".join(RETRIB_HDR) + "\n" + "\n".join(ej) + "\n"
