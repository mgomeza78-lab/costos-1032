# -*- coding: utf-8 -*-
"""Ingesta y validación de los CSV del cargue mensual.

Cada función recibe el contenido del CSV y lo inserta (upsert) en su tabla, DENTRO de la
conexión con el alcance RLS fijado. Por seguridad, el `empresa_id` siempre lo fija la ruta
(el tenant autenticado); la columna «empresa» del archivo se ignora, de modo que un archivo
no puede escribir en otra empresa aunque la nombre. Cada fila va en un SAVEPOINT: una fila
inválida (o bloqueada por RLS) se descarta sin tumbar las demás.
"""
import csv
import io
import re
from collections import defaultdict, Counter
from sqlalchemy import text

# Columnas del reporte de Facturación del SUI por servicio, mapeadas al concepto del estudio.
# El SUI tiene DOS esquemas vigentes: el "clásico" (CLASEUSO, LECT_CONSUMO, …, con sufijo _NN)
# y uno nuevo en camelCase (codigoClaseUso, consumoM3, …). Cada concepto lista sus alias EN
# MAYÚSCULAS y sin el sufijo _NN (como los deja _mapa_base); se toma el primer alias presente.
# Confirmados contra archivos reales de Las Ceibas (AC y ALC, años 2024–2026).
CAMPOS_SUI = {
    "acueducto": {
        "clase": ["CLASEUSO", "CODIGOCLASEUSO"],
        "cons":  ["LECT_CONSUMO", "CONSUMOM3"],
        "sub":   ["CONS_SUB", "CONSUMOSUBSIDIADOM3"],
        "fcf":   ["FACTORSUBSIDIOCARGOFIJO", "FACTORSUBSIDIOCONTRIBUCIONCARGOFIJO"],
        "fcc":   ["FACTORSUBSIDIOCONSUMO", "FACTORSUBSIDIOCONTRIBUCIONCONSUMO"],
    },
    "alcantarillado": {
        "clase": ["CLASEUSO", "CODIGOCLASEUSO"],
        "cons":  ["VERTIMIENTO", "VERTIMIENTOM3"],
        "sub":   ["VERTIMIENTOSUB", "VERTIMIENTOSUBSIDIADOM3"],
        "fcf":   ["FACTORSUBCONTCFIJO", "FACTORSUBSIDIOCONTRIBUCIONCARGOFIJO"],
        "fcc":   ["FACTORSUBSIDIOVERTIMIENTO", "FACTORSUBSIDIOCONTRIBUCIONCONSUMO"],
    },
}
# Conceptos imprescindibles para agregar por clase; los factores de subsidio son opcionales.
CAMPOS_SUI_REQ = {"clase", "cons", "sub"}
_SUFIJO = re.compile(r"_\d+$")

_SERV = {"AC": "acueducto", "AL": "alcantarillado",
         "ACUEDUCTO": "acueducto", "ALCANTARILLADO": "alcantarillado"}


def _norm_serv(s):
    return _SERV.get((s or "").strip().upper())


_MESES_NOMBRE = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def mes_de_nombre(nombre):
    """Deduce el mes (1..12) del nombre de un archivo del SUI; None si no se reconoce.
    Acepta 'JUNIO', 'jun', '2026-06', o un '06' suelto en el nombre."""
    n = (nombre or "").lower()
    m = re.search(r"20\d\d[-_. ]?(0[1-9]|1[0-2])(?:\D|$)", n)      # AAAA-MM
    if m:
        return int(m.group(1))
    for i, nm in enumerate(_MESES_NOMBRE, 1):
        if nm in n or nm[:3] in n:                                 # nombre completo o 3 letras
            return i
    m = re.search(r"(?:^|\D)(0[1-9]|1[0-2])(?:\D|$)", n)           # MM suelto
    return int(m.group(1)) if m else None


def _sep(linea):
    """Separador más probable de una línea de encabezado: coma, punto y coma o tabulador.
    Los reportes reexportados en Excel con configuración regional colombiana salen con ';'."""
    return max((",", ";", "\t"), key=linea.count)


def _rows(contenido):
    # Normaliza TODOS los saltos de línea (\r\n, \r solo de Excel/Mac, \n) para que csv no
    # vea un '\r' dentro de un campo ("new-line character seen in unquoted field"), y quita
    # el BOM inicial que suelen traer los CSV exportados por Excel/Windows.
    texto = contenido.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    # Detecta el separador por la primera línea con contenido (por defecto, coma).
    primera = next((l for l in texto.split("\n") if l.strip()), "")
    return list(csv.DictReader(io.StringIO(texto), delimiter=_sep(primera)))


def _num(x):
    x = (x or "").strip().replace(",", ".")
    return float(x) if x != "" else None


def _int(x):
    v = _num(x)
    return int(round(v)) if v is not None else None


def _faltan(rows, req):
    if not rows:
        return ["el archivo está vacío o sin encabezado"]
    cols = set(h.strip() for h in rows[0].keys() if h)
    faltan = req - cols
    return [f"faltan columnas: {', '.join(sorted(faltan))}"] if faltan else []


def _ins(conn, sql, params):
    """Ejecuta un upsert en un SAVEPOINT. Devuelve (ok, mensaje_error)."""
    try:
        with conn.begin_nested():
            conn.execute(text(sql), params)
        return True, None
    except Exception as ex:
        return False, type(ex).__name__


def cargar_indices(conn, contenido):
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "ipc"})):
        return 0, e
    ok, err = 0, []
    sql = ("INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) "
           "VALUES (:a,:m,:ipc,:ipcs,'DANE','reportada') "
           "ON CONFLICT (anio,mes) DO UPDATE SET indice=excluded.indice, ipcs=excluded.ipcs, "
           "fuente=excluded.fuente, procedencia=excluded.procedencia")
    for i, r in enumerate(rows, 2):
        # ipc_sar = IPC sin alimentos ni regulados (alias aceptado de ipcs)
        sar = r.get("ipcs") or r.get("ipc_sar")
        good, msg = _ins(conn, sql, {"a": _int(r["anio"]), "m": _int(r["mes"]),
                                     "ipc": _num(r["ipc"]),
                                     "ipcs": _num(sar) if sar else None})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


def cargar_comercial(conn, empresa_id, contenido):
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "servicio", "clase", "suscriptores", "m3", "m3_subsidiable"})):
        return 0, e
    ok, err = 0, []
    sql = ("INSERT INTO carga_mensual_detalle(empresa_id,anio,mes,servicio,clase,"
           "suscriptores,m3,m3_subsidiable,origen) VALUES (:e,:a,:m,:s,:c,:su,:m3,:ms,'SUI') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,clase) DO UPDATE SET "
           "suscriptores=excluded.suscriptores, m3=excluded.m3, "
           "m3_subsidiable=excluded.m3_subsidiable, origen=excluded.origen")
    for i, r in enumerate(rows, 2):
        serv = _norm_serv(r["servicio"])
        if not serv:
            err.append(f"fila {i}: servicio inválido '{r['servicio']}'")
            continue
        m3, m3s = _num(r["m3"]), _num(r["m3_subsidiable"])
        if m3 is not None and m3s is not None and m3s > m3 + 1e-6:
            err.append(f"fila {i}: m3_subsidiable > m3")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r["anio"]), "m": _int(r["mes"]),
                                     "s": serv, "c": _int(r["clase"]), "su": _int(r["suscriptores"]),
                                     "m3": m3, "ms": m3s})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


def cargar_factores(conn, empresa_id, contenido):
    rows = _rows(contenido)
    if (e := _faltan(rows, {"vigencia", "servicio", "clase", "factor_cargofijo", "factor_consumo"})):
        return 0, e
    ok, err = 0, []
    sql = ("INSERT INTO factor_subsidio(empresa_id,vigencia,servicio,clase,factor_cargofijo,factor_consumo) "
           "VALUES (:e,:v,:s,:c,:fcf,:fc) "
           "ON CONFLICT (empresa_id,vigencia,servicio,clase) DO UPDATE SET "
           "factor_cargofijo=excluded.factor_cargofijo, factor_consumo=excluded.factor_consumo")
    for i, r in enumerate(rows, 2):
        serv = _norm_serv(r["servicio"])
        if not serv:
            err.append(f"fila {i}: servicio inválido '{r['servicio']}'")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "v": _int(r["vigencia"]), "s": serv,
                                     "c": _int(r["clase"]), "fcf": _num(r["factor_cargofijo"]),
                                     "fc": _num(r["factor_consumo"])})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


def cargar_indicadores(conn, empresa_id, contenido):
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "servicio"})):
        return 0, e
    ok, err = 0, []
    sql = ("INSERT INTO indicador_mensual(empresa_id,anio,mes,servicio,ipuf_real,continuidad_h,"
           "irca,reclamaciones,cortes,reconexiones) VALUES (:e,:a,:m,:s,:ip,:co,:ir,:re,:ct,:rc) "
           "ON CONFLICT (empresa_id,anio,mes,servicio) DO UPDATE SET ipuf_real=excluded.ipuf_real, "
           "continuidad_h=excluded.continuidad_h, irca=excluded.irca, "
           "reclamaciones=excluded.reclamaciones, cortes=excluded.cortes, reconexiones=excluded.reconexiones")
    for i, r in enumerate(rows, 2):
        serv = _norm_serv(r["servicio"])
        if not serv:
            err.append(f"fila {i}: servicio inválido '{r['servicio']}'")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r["anio"]), "m": _int(r["mes"]),
                                     "s": serv, "ip": _num(r.get("ipuf_real")),
                                     "co": _num(r.get("continuidad_h")), "ir": _num(r.get("irca")),
                                     "re": _int(r.get("reclamaciones")), "ct": _int(r.get("cortes")),
                                     "rc": _int(r.get("reconexiones"))})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


def _mapa_base(fieldnames):
    """BASENAME (sin _NN, en mayúsculas) -> encabezado real."""
    m = {}
    for h in fieldnames:
        if h:
            m[_SUFIJO.sub("", h.strip()).upper()] = h
    return m


def _resolver_campos(cols, cfg, requeridos):
    """Resuelve cada concepto del reporte del SUI al encabezado real presente, probando sus
    alias (esquema clásico y esquema nuevo). Devuelve ({concepto: encabezado|None}, faltan),
    donde `faltan` son los conceptos requeridos que ningún alias logró cubrir."""
    campos, faltan = {}, []
    for concepto, aliases in cfg.items():
        campos[concepto] = next((cols[a] for a in aliases if a in cols), None)
        if campos[concepto] is None and concepto in requeridos:
            faltan.append(concepto)
    return campos, faltan


def cargar_facturacion_sui(conn, empresa_id, servicio, anio, mes, contenido):
    """Importa el archivo ORIGINAL del SUI (Facturación por suscriptor) y lo agrega por
    clase de uso → carga_mensual_detalle + factor_subsidio. El servicio, año y mes los fija
    el usuario al subir (el archivo no trae un período único)."""
    serv = _norm_serv(servicio)
    if serv not in CAMPOS_SUI:
        return 0, ["servicio inválido"]
    rows = _rows(contenido)
    if not rows:
        return 0, ["el archivo está vacío"]
    cols = _mapa_base(rows[0].keys())
    campos, faltan = _resolver_campos(cols, CAMPOS_SUI[serv], CAMPOS_SUI_REQ)
    if faltan:
        etq = {"clase": "clase de uso", "cons": "consumo/vertimiento (m³)",
               "sub": "consumo subsidiable (m³)", "fcf": "factor subsidio cargo fijo",
               "fcc": "factor subsidio consumo"}
        det = ", ".join(etq.get(c, c) for c in faltan)
        return 0, [f"no se reconoció el reporte de {serv}: faltan columnas de {det}; "
                   f"verifica que sea el CSV original del SUI (no un Excel .xlsx)"]
    agg = defaultdict(lambda: {"n": 0, "m3": 0.0, "sub": 0.0, "fcf": Counter(), "fcc": Counter()})
    for r in rows:
        clv = _int(r.get(campos["clase"]))
        if clv is None:
            continue
        a = agg[clv]
        a["n"] += 1
        a["m3"] += _num(r.get(campos["cons"])) or 0.0
        a["sub"] += _num(r.get(campos["sub"])) or 0.0
        fcf = _num(r.get(campos["fcf"])) if campos["fcf"] else None
        fcc = _num(r.get(campos["fcc"])) if campos["fcc"] else None
        if fcf is not None:
            a["fcf"][fcf] += 1
        if fcc is not None:
            a["fcc"][fcc] += 1
    sql_d = ("INSERT INTO carga_mensual_detalle(empresa_id,anio,mes,servicio,clase,"
             "suscriptores,m3,m3_subsidiable,origen) VALUES (:e,:a,:m,:s,:c,:su,:m3,:ms,'SUI') "
             "ON CONFLICT (empresa_id,anio,mes,servicio,clase) DO UPDATE SET "
             "suscriptores=excluded.suscriptores, m3=excluded.m3, "
             "m3_subsidiable=excluded.m3_subsidiable, origen=excluded.origen")
    sql_f = ("INSERT INTO factor_subsidio(empresa_id,vigencia,servicio,clase,factor_cargofijo,factor_consumo) "
             "VALUES (:e,:v,:s,:c,:fcf,:fc) ON CONFLICT (empresa_id,vigencia,servicio,clase) "
             "DO UPDATE SET factor_cargofijo=excluded.factor_cargofijo, factor_consumo=excluded.factor_consumo")
    ok, err = 0, []
    for clase, a in sorted(agg.items()):
        good, msg = _ins(conn, sql_d, {"e": empresa_id, "a": anio, "m": mes, "s": serv, "c": clase,
                                       "su": a["n"], "m3": a["m3"], "ms": a["sub"]})
        if not good:
            err.append(f"clase {clase}: {msg}")
            continue
        fcf = a["fcf"].most_common(1)[0][0] if a["fcf"] else None
        fcc = a["fcc"].most_common(1)[0][0] if a["fcc"] else None
        _ins(conn, sql_f, {"e": empresa_id, "v": anio, "s": serv, "c": clase, "fcf": fcf, "fc": fcc})
        ok += 1
    return ok, err


def cargar_macromedicion(conn, empresa_id, contenido):
    """CSV de macromedición (agua producida por punto, mensual). Columnas:
    anio, mes, servicio, punto, m3_producido [, m3_bloque_entregado, m3_bloque_recibido]."""
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "servicio", "punto", "m3_producido"})):
        return 0, e
    ok, err = 0, []
    sql = ("INSERT INTO macromedicion(empresa_id,anio,mes,servicio,punto,m3_producido,"
           "m3_bloque_entregado,m3_bloque_recibido,origen) "
           "VALUES (:e,:a,:m,:s,:p,:mp,:be,:br,'propio') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,punto) DO UPDATE SET "
           "m3_producido=excluded.m3_producido, m3_bloque_entregado=excluded.m3_bloque_entregado, "
           "m3_bloque_recibido=excluded.m3_bloque_recibido")
    for i, r in enumerate(rows, 2):
        serv = _norm_serv(r["servicio"])
        if not serv:
            err.append(f"fila {i}: servicio inválido '{r['servicio']}'")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r["anio"]), "m": _int(r["mes"]),
                                     "s": serv, "p": (r.get("punto") or "").strip(),
                                     "mp": _num(r["m3_producido"]),
                                     "be": _num(r.get("m3_bloque_entregado")),
                                     "br": _num(r.get("m3_bloque_recibido"))})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


# Mapa concepto del clasificador -> concepto del numerador mensual.
_CONCEPTO_NUM = {"CACe": "CACe", "COCe_comparables": "COCe", "CE_contable": "CE",
                 "CIQ_contable": "CIQ", "COIR": "COIR", "ICTA": "ICTA", "ICTO": "ITO", "TA": "TA"}


def persistir_numeradores_mensual(conn, empresa_id, anio, mes, numeradores, split_ac):
    """Guarda los numeradores del balance del mes en numerador_mensual, repartidos por
    servicio con `split_ac` (concepto -> participación de acueducto, 0..1). El resto va a
    alcantarillado. `numeradores` = salida de clasificador.numeradores()."""
    sql = ("INSERT INTO numerador_mensual(empresa_id,anio,mes,servicio,concepto,valor,origen) "
           "VALUES (:e,:a,:m,:s,:c,:v,'balance') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,concepto) DO UPDATE SET "
           "valor=excluded.valor, origen=excluded.origen")
    n = 0
    for k_cl, concepto in _CONCEPTO_NUM.items():
        total = float(numeradores.get(k_cl, 0.0) or 0.0)
        if total == 0.0 and concepto not in ("CACe", "COCe"):
            continue
        sa = split_ac.get(concepto, 1.0)
        for serv, val in (("acueducto", total * sa), ("alcantarillado", total * (1 - sa))):
            good, _ = _ins(conn, sql, {"e": empresa_id, "a": anio, "m": mes, "s": serv,
                                       "c": concepto, "v": val})
            n += 1 if good else 0
    return n


TIPOS = {"comercial": cargar_comercial, "factores": cargar_factores,
         "indicadores": cargar_indicadores, "macromedicion": cargar_macromedicion}
