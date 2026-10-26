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
# `muni` (opcional): columna del municipio/DANE del reporte, para desagregar por APS. Si el
# reporte la trae, suscriptores y m³ se reparten por APS (la llave coincide con `divipola`).
_MUNI_ALIASES = ["DIVIPOLA", "DANE", "CODDANE", "CODIGODANE", "CODMUNICIPIO", "CODIGOMUNICIPIO",
                 "IDMUNICIPIO", "MUNICIPIO", "MUNICIPIODANE", "CODIGODIVIPOLA", "CODIGOMPIO", "MPIO",
                 "CODMPIO", "CODIGOMUNICIPIODANE"]
CAMPOS_SUI = {
    "acueducto": {
        "clase": ["CLASEUSO", "CODIGOCLASEUSO"],
        "cons":  ["LECT_CONSUMO", "CONSUMOM3"],
        "sub":   ["CONS_SUB", "CONSUMOSUBSIDIADOM3"],
        "fcf":   ["FACTORSUBSIDIOCARGOFIJO", "FACTORSUBSIDIOCONTRIBUCIONCARGOFIJO"],
        "fcc":   ["FACTORSUBSIDIOCONSUMO", "FACTORSUBSIDIOCONTRIBUCIONCONSUMO"],
        "muni":  _MUNI_ALIASES,
    },
    "alcantarillado": {
        "clase": ["CLASEUSO", "CODIGOCLASEUSO"],
        "cons":  ["VERTIMIENTO", "VERTIMIENTOM3"],
        "sub":   ["VERTIMIENTOSUB", "VERTIMIENTOSUBSIDIADOM3"],
        "fcf":   ["FACTORSUBCONTCFIJO", "FACTORSUBSIDIOCONTRIBUCIONCARGOFIJO"],
        "fcc":   ["FACTORSUBSIDIOVERTIMIENTO", "FACTORSUBSIDIOCONTRIBUCIONCONSUMO"],
        "muni":  _MUNI_ALIASES,
    },
}
# Conceptos imprescindibles para agregar por clase; factores de subsidio y municipio son opcionales.
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


def _preparar(contenido):
    """Normaliza saltos de línea (\\r\\n, \\r de Excel/Mac), quita el BOM inicial y detecta el
    separador por la primera línea. Devuelve (texto, separador). No parte todo el texto."""
    texto = contenido.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    return texto, _sep(texto.split("\n", 1)[0])


# Caracteres de control (salvo tab, salto de línea y retorno) que no aparecen en un CSV sano.
_CTRL = {chr(c) for c in range(32)} - {"\t", "\n", "\r"}


def _es_binario(texto):
    """True si el contenido no parece texto CSV: archivo dañado, un .xlsx, o un comprimido
    renombrado a .csv. Evita intentar parsear 20 MB de binario (y agotar la memoria)."""
    m = texto[:8192]
    if not m:
        return False
    if "\x00" in m:
        return True
    return sum(1 for c in m if c in _CTRL) / len(m) > 0.02


def _rows(contenido):
    # Normaliza saltos de línea y BOM, detecta el separador (coma/;/tab) y materializa las filas
    # (para archivos pequeños: IPC, factores, macromedición, etc.). Los encabezados se normalizan
    # a minúsculas y sin espacios, de modo que 'Servicio', 'SERVICIO' y 'servicio' son equivalentes.
    texto, sep = _preparar(contenido)
    out = []
    for r in csv.DictReader(io.StringIO(texto), delimiter=sep):
        out.append({(k.strip().lower() if k else k): v for k, v in r.items()})
    return out


def _num(x):
    x = (x or "").strip().replace(",", ".")
    return float(x) if x != "" else None


def _int(x):
    v = _num(x)
    return int(round(v)) if v is not None else None


def _mes_cell(x):
    """Mes (1..12) desde una celda: número ('1', '01', '1.0') o nombre en español
    ('Enero', 'ENE', 'ene'). None si no se reconoce."""
    s = str(x or "").strip()
    if not s:
        return None
    try:
        v = int(round(float(s.replace(",", "."))))
        if 1 <= v <= 12:
            return v
    except ValueError:
        pass
    n = s.lower()
    for i, nm in enumerate(_MESES_NOMBRE, 1):
        if n == nm or (len(n) >= 3 and nm.startswith(n[:3])):
            return i
    return None


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
        good, msg = _ins(conn, sql, {"a": _int(r["anio"]), "m": _mes_cell(r.get("mes")),
                                     "ipc": _num(r["ipc"]),
                                     "ipcs": _num(sar) if sar else None})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


def cargar_comercial(conn, empresa_id, contenido):
    """CSV comercial propio por clase. Columnas: anio, mes, servicio, clase, suscriptores, m3,
    m3_subsidiable [, aps]. `aps` (opcional) reparte por APS (nombre del municipio o código DANE;
    vacío = conjunto). La llave coincide con `divipola`."""
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "servicio", "clase", "suscriptores", "m3", "m3_subsidiable"})):
        return 0, e
    cols = [h for h in rows[0].keys() if h]
    col_aps = _col_aps(cols)
    mapa = aps_mapa(conn, empresa_id) if col_aps else {}
    # Reemplazo limpio: borra el detalle previo de cada (anio,mes,servicio) presente en el archivo,
    # para que un re-cargue que cambie la granularidad por APS no deje filas huérfanas.
    combos = {(_int(r.get("anio")), _mes_cell(r.get("mes")), _norm_serv(r.get("servicio")))
              for r in rows}
    for a, m, s in combos:
        if a and m and s:
            conn.execute(text("DELETE FROM carga_mensual_detalle WHERE empresa_id=:e AND anio=:a "
                              "AND mes=:m AND servicio=:s"), {"e": empresa_id, "a": a, "m": m, "s": s})
    ok, err = 0, []
    sql = ("INSERT INTO carga_mensual_detalle(empresa_id,anio,mes,servicio,clase,cod_dane,"
           "suscriptores,m3,m3_subsidiable,origen) VALUES (:e,:a,:m,:s,:c,:cd,:su,:m3,:ms,'SUI') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,clase,cod_dane) DO UPDATE SET "
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
        cod, eaps = (_resolver_aps(r.get(col_aps), mapa) if col_aps else ("", None))
        if eaps:
            err.append(f"fila {i}: {eaps}")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r["anio"]), "m": _mes_cell(r.get("mes")),
                                     "s": serv, "c": _int(r["clase"]), "cd": cod, "su": _int(r["suscriptores"]),
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
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r["anio"]), "m": _mes_cell(r.get("mes")),
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
    texto, sep = _preparar(contenido)
    if _es_binario(texto):
        return 0, ["el archivo no parece un CSV de texto (¿está dañado, o es un Excel .xlsx / "
                   "comprimido renombrado a .csv?); vuelve a descargar el reporte del SUI"]
    reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
    if not reader.fieldnames:
        return 0, ["el archivo está vacío"]
    cols = _mapa_base(reader.fieldnames)
    campos, faltan = _resolver_campos(cols, CAMPOS_SUI[serv], CAMPOS_SUI_REQ)
    if faltan:
        etq = {"clase": "clase de uso", "cons": "consumo/vertimiento (m³)",
               "sub": "consumo subsidiable (m³)", "fcf": "factor subsidio cargo fijo",
               "fcc": "factor subsidio consumo"}
        det = ", ".join(etq.get(c, c) for c in faltan)
        return 0, [f"no se reconoció el reporte de {serv}: faltan columnas de {det}; "
                   f"verifica que sea el CSV original del SUI (no un Excel .xlsx)"]
    # Si el reporte trae municipio/DANE, se reparte por APS (la llave coincide con `divipola`);
    # el municipio que no corresponda a un APS de la empresa cae en el conjunto ('').
    mapa = aps_mapa(conn, empresa_id) if campos.get("muni") else {}
    # Agregación en streaming (no materializa toda la lista): clave para los archivos de ~30 MB.
    #  · agg_q: cantidades por (clase, cod_dane) — alimenta el detalle por APS.
    #  · agg_f: factores por clase (los factores no dependen del APS).
    agg_q = defaultdict(lambda: {"n": 0, "m3": 0.0, "sub": 0.0})
    agg_f = defaultdict(lambda: {"fcf": Counter(), "fcc": Counter()})
    for r in reader:
        clv = _int(r.get(campos["clase"]))
        if clv is None:
            continue
        cod = ""
        if campos.get("muni"):
            cod, _e = _resolver_aps(r.get(campos["muni"]), mapa)
            cod = cod or ""          # municipio no reconocido -> conjunto (sin perder el dato)
        a = agg_q[(clv, cod)]
        a["n"] += 1
        a["m3"] += _num(r.get(campos["cons"])) or 0.0
        a["sub"] += _num(r.get(campos["sub"])) or 0.0
        f = agg_f[clv]
        fcf = _num(r.get(campos["fcf"])) if campos["fcf"] else None
        fcc = _num(r.get(campos["fcc"])) if campos["fcc"] else None
        if fcf is not None:
            f["fcf"][fcf] += 1
        if fcc is not None:
            f["fcc"][fcc] += 1
    sql_d = ("INSERT INTO carga_mensual_detalle(empresa_id,anio,mes,servicio,clase,cod_dane,"
             "suscriptores,m3,m3_subsidiable,origen) VALUES (:e,:a,:m,:s,:c,:cd,:su,:m3,:ms,'SUI') "
             "ON CONFLICT (empresa_id,anio,mes,servicio,clase,cod_dane) DO UPDATE SET "
             "suscriptores=excluded.suscriptores, m3=excluded.m3, "
             "m3_subsidiable=excluded.m3_subsidiable, origen=excluded.origen")
    sql_f = ("INSERT INTO factor_subsidio(empresa_id,vigencia,servicio,clase,factor_cargofijo,factor_consumo) "
             "VALUES (:e,:v,:s,:c,:fcf,:fc) ON CONFLICT (empresa_id,vigencia,servicio,clase) "
             "DO UPDATE SET factor_cargofijo=excluded.factor_cargofijo, factor_consumo=excluded.factor_consumo")
    # Reemplazo limpio del mes/servicio: borra el detalle previo (cualquier APS) para que un
    # re-cargue que cambie la granularidad por APS no deje filas huérfanas que dupliquen la suma.
    conn.execute(text("DELETE FROM carga_mensual_detalle WHERE empresa_id=:e AND anio=:a "
                      "AND mes=:m AND servicio=:s"), {"e": empresa_id, "a": anio, "m": mes, "s": serv})
    # Detalle por (clase, APS). Si no hubo columna de municipio, todo queda en el conjunto ('').
    ok, err = 0, []
    for (clase, cod), a in sorted(agg_q.items()):
        good, msg = _ins(conn, sql_d, {"e": empresa_id, "a": anio, "m": mes, "s": serv, "c": clase,
                                       "cd": cod, "su": a["n"], "m3": a["m3"], "ms": a["sub"]})
        if not good:
            err.append(f"clase {clase}{(' · '+cod) if cod else ''}: {msg}")
            continue
        ok += 1
    # Factores de subsidio por clase (no dependen del APS).
    for clase, f in sorted(agg_f.items()):
        fcf = f["fcf"].most_common(1)[0][0] if f["fcf"] else None
        fcc = f["fcc"].most_common(1)[0][0] if f["fcc"] else None
        _ins(conn, sql_f, {"e": empresa_id, "v": anio, "s": serv, "c": clase, "fcf": fcf, "fc": fcc})
    # Resumen del mes en carga_mensual (conjunto, cod_dane=''): total de suscriptores y m³
    # agregando TODAS las clases y APS. Es lo que leen Validación, Resultados y el listado.
    if ok:
        tot_susc = sum(a["n"] for a in agg_q.values())
        tot_m3 = sum(a["m3"] for a in agg_q.values())
        _ins(conn,
             "INSERT INTO carga_mensual(empresa_id,anio,mes,servicio,cod_dane,suscriptores,m3_facturados,origen) "
             "VALUES (:e,:a,:m,:s,'',:su,:m3,'SUI') "
             "ON CONFLICT (empresa_id,anio,mes,servicio,cod_dane) DO UPDATE SET "
             "suscriptores=excluded.suscriptores, m3_facturados=excluded.m3_facturados, "
             "origen=excluded.origen, cargado_en=now()",
             {"e": empresa_id, "a": anio, "m": mes, "s": serv, "su": tot_susc, "m3": tot_m3})
    return ok, err


# Columnas que, en un archivo de cargue, identifican el APS (municipio) de la fila.
_APS_COLS = ("aps", "cod_dane", "codigo_dane", "coddane", "dane", "divipola", "municipio")


def aps_mapa(conn, empresa_id):
    """Resolvedor de APS de la empresa: dict {clave -> cod_dane} con el código DANE y el
    nombre del municipio (en minúsculas) como claves. Permite que un archivo identifique el
    APS por código DANE o por nombre del municipio atendido (art. 2.1.2.1.1.5)."""
    m = {}
    for cod, nom in conn.execute(text(
            "SELECT m.cod_dane, m.nombre FROM empresa_municipio em "
            "JOIN municipio m ON m.cod_dane = em.cod_dane WHERE em.empresa_id=:e"),
            {"e": empresa_id}).all():
        cod = (cod or "").strip()
        if not cod:
            continue
        m[cod] = cod
        m[cod.lstrip("0")] = cod            # por si el DANE viene sin ceros a la izquierda
        if nom:
            m[nom.strip().lower()] = cod
    return m


def _col_aps(cols):
    return next((c for c in _APS_COLS if c in cols), None)


def _resolver_aps(valor, mapa):
    """(cod_dane, error). '' = conjunto/todas las APS cuando la celda viene vacía."""
    v = (valor or "").strip()
    if v == "":
        return "", None
    cod = mapa.get(v) or mapa.get(v.lower()) or mapa.get(v.lstrip("0"))
    if cod:
        return cod, None
    return None, f"APS no reconocida '{v}' (use el código DANE o el nombre del municipio atendido)"


def cargar_macromedicion(conn, empresa_id, contenido):
    """CSV de macromedición (agua producida por punto, mensual). Columnas:
    anio, mes, servicio, punto, m3_producido [, m3_bloque_entregado, m3_bloque_recibido, aps].
    `aps` (o cod_dane/municipio) es opcional: identifica el APS del punto (código DANE o nombre
    del municipio); vacío = conjunto/todas las APS. Tolera encabezados en mayúsculas, meses por
    nombre ('Enero') y variantes o erratas de la columna de producción (cualquier m3_* no bloque)."""
    rows = _rows(contenido)
    if (e := _faltan(rows, {"anio", "mes", "servicio", "punto"})):
        return 0, e
    cols = [h for h in rows[0].keys() if h]
    col_prod = ("m3_producido" if "m3_producido" in cols
                else next((c for c in cols if c.startswith("m3") and "bloque" not in c), None))
    if not col_prod:
        return 0, ["faltan columnas: m3_producido"]
    col_aps = _col_aps(cols)
    mapa = aps_mapa(conn, empresa_id) if col_aps else {}
    ok, err = 0, []
    sql = ("INSERT INTO macromedicion(empresa_id,anio,mes,servicio,punto,cod_dane,m3_producido,"
           "m3_bloque_entregado,m3_bloque_recibido,origen) "
           "VALUES (:e,:a,:m,:s,:p,:cd,:mp,:be,:br,'propio') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,punto,cod_dane) DO UPDATE SET "
           "m3_producido=excluded.m3_producido, m3_bloque_entregado=excluded.m3_bloque_entregado, "
           "m3_bloque_recibido=excluded.m3_bloque_recibido")
    for i, r in enumerate(rows, 2):
        serv = _norm_serv(r.get("servicio"))
        if not serv:
            err.append(f"fila {i}: servicio inválido '{r.get('servicio')}'")
            continue
        mes = _mes_cell(r.get("mes"))
        if mes is None:
            err.append(f"fila {i}: mes inválido '{r.get('mes')}'")
            continue
        cod_dane, eaps = (_resolver_aps(r.get(col_aps), mapa) if col_aps else ("", None))
        if eaps:
            err.append(f"fila {i}: {eaps}")
            continue
        good, msg = _ins(conn, sql, {"e": empresa_id, "a": _int(r.get("anio")), "m": mes,
                                     "s": serv, "p": (r.get("punto") or "").strip(), "cd": cod_dane,
                                     "mp": _num(r.get(col_prod)),
                                     "be": _num(r.get("m3_bloque_entregado")),
                                     "br": _num(r.get("m3_bloque_recibido"))})
        ok += 1 if good else 0
        if not good:
            err.append(f"fila {i}: {msg}")
    return ok, err


# Mapa concepto del clasificador -> concepto del numerador mensual.
_CONCEPTO_NUM = {"CACe": "CACe", "COCe_comparables": "COCe", "CE_contable": "CE",
                 "CIQ_contable": "CIQ", "COIR": "COIR", "ICTA": "ICTA", "ICTO": "ITO", "TA": "TA"}


def persistir_numeradores_mensual(conn, empresa_id, anio, mes, numeradores, split_ac, cod_dane=""):
    """Guarda los numeradores del balance del mes en numerador_mensual, repartidos por
    servicio con `split_ac` (concepto -> participación de acueducto, 0..1). El resto va a
    alcantarillado. `numeradores` = salida de clasificador.numeradores().

    `cod_dane` identifica el APS del balance: '' = conjunto / todas las APS (lo normal).
    Para mantener la coherencia del total (que es la SUMA sobre cod_dane), un mes es conjunto
    O está repartido por APS, nunca ambos: al cargar el conjunto se borra cualquier reparto por
    APS del mes; al cargar un APS se borra el conjunto de ese mes (y se reemplaza ese APS)."""
    cod_dane = (cod_dane or "").strip()
    if cod_dane == "":
        conn.execute(text("DELETE FROM numerador_mensual WHERE empresa_id=:e AND anio=:a AND mes=:m"),
                     {"e": empresa_id, "a": anio, "m": mes})
    else:
        conn.execute(text("DELETE FROM numerador_mensual WHERE empresa_id=:e AND anio=:a AND mes=:m "
                          "AND cod_dane IN ('', :cd)"), {"e": empresa_id, "a": anio, "m": mes, "cd": cod_dane})
    sql = ("INSERT INTO numerador_mensual(empresa_id,anio,mes,servicio,concepto,cod_dane,valor,origen) "
           "VALUES (:e,:a,:m,:s,:c,:cd,:v,'balance') "
           "ON CONFLICT (empresa_id,anio,mes,servicio,concepto,cod_dane) DO UPDATE SET "
           "valor=excluded.valor, origen=excluded.origen")
    n = 0
    for k_cl, concepto in _CONCEPTO_NUM.items():
        total = float(numeradores.get(k_cl, 0.0) or 0.0)
        if total == 0.0 and concepto not in ("CACe", "COCe"):
            continue
        sa = split_ac.get(concepto, 1.0)
        for serv, val in (("acueducto", total * sa), ("alcantarillado", total * (1 - sa))):
            good, _ = _ins(conn, sql, {"e": empresa_id, "a": anio, "m": mes, "s": serv,
                                       "c": concepto, "cd": cod_dane, "v": val})
            n += 1 if good else 0
    return n


TIPOS = {"comercial": cargar_comercial, "factores": cargar_factores,
         "indicadores": cargar_indicadores, "macromedicion": cargar_macromedicion}
