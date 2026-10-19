# -*- coding: utf-8 -*-
"""Lector flexible de Balance de Prueba — independiente del software contable.

Cada empresa exporta el balance con columnas/encabezados/formatos distintos (Integrasoft,
SIIGO, World Office, Helisa, SAP…). Lo común es el **código del PUC** (clase 5 gasto, 7 costo).
Este lector **auto-detecta** la hoja, la fila de encabezado y las columnas (código, nombre,
saldos) por su etiqueta —sin tildes ni mayúsculas— y **normaliza el código** quitando puntos y
espacios, de modo que `5.1.01.01` y `51010 1` queden como el mismo código canónico. Admite
además un **perfil por empresa** para forzar el mapeo cuando la auto-detección no baste.
"""
import io
import re
import unicodedata

CANON = ["saldo_inicial", "debito", "credito", "saldo_final"]
_ALIAS = {
    "codigo": ["codigo cuenta", "cuenta contable", "cuenta puc", "codigo", "cuenta", "cod"],
    "nombre": ["nombre cuenta", "descripcion", "nombre", "detalle", "concepto"],
    "saldo_inicial": ["saldo inicial", "saldo anterior"],
    "debito": ["movimiento debito", "total debito", "debitos", "debito", "debe"],
    "credito": ["movimiento credito", "total credito", "creditos", "credito", "haber"],
    "saldo_final": ["saldo final", "saldo actual", "nuevo saldo", "saldo"],
}


def _sinacentos(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def norm_codigo(s):
    """Código canónico del PUC: solo dígitos (quita puntos, espacios, guiones)."""
    return re.sub(r"\D", "", str(s or ""))


def _es_codigo(v):
    s = str(v or "").strip()
    return bool(s) and bool(re.fullmatch(r"\d[\d.\-\s]*", s)) and len(norm_codigo(s)) >= 1


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(" ", "")
    # miles '.' y decimal ',' -> normalizar si corresponde
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _detectar(rows, perfil=None):
    """Devuelve (fila_encabezado, {campo: idx_columna})."""
    perfil = perfil or {}
    # 1) fila de encabezado: la primera con 'nombre' y algún 'saldo'
    hr = None
    for i, r in enumerate(rows[:25]):
        etiquetas = [_sinacentos(c) for c in r]
        txt = " | ".join(etiquetas)
        if any(a in txt for a in ["nombre", "descripcion"]) and "saldo" in txt:
            hr = i
            break
    if hr is None:
        hr = 0
    header = [_sinacentos(c) for c in rows[hr]]
    # asignación por columna: cada columna toma el campo cuyo alias calza más largo;
    # cada campo lo gana la primera columna que mejor lo calza (evita colisiones por "saldo").
    cols = dict(perfil) if perfil else {}
    for j, h in enumerate(header):
        if not h:
            continue
        mejor_campo, mejor_len = None, 0
        for campo, alias in _ALIAS.items():
            for a in alias:
                if (h == a or h.startswith(a)) and len(a) > mejor_len:
                    mejor_campo, mejor_len = campo, len(a)
        if mejor_campo and mejor_campo not in cols:
            cols[mejor_campo] = j
    # 2) si no se halló la columna de código por etiqueta, detectarla por contenido
    if "codigo" not in cols:
        best, score = None, -1
        for j in range(len(header)):
            s = sum(1 for r in rows[hr + 1:hr + 60] if j < len(r) and _es_codigo(r[j]))
            if s > score:
                best, score = j, s
        cols["codigo"] = best
    if "nombre" not in cols and cols.get("codigo") is not None:
        cols["nombre"] = cols["codigo"] + 1
    return hr, cols


def leer_filas(rows, perfil=None):
    """rows = lista de tuplas (de openpyxl o csv). Devuelve filas canónicas."""
    hr, cols = _detectar(rows, perfil)
    out = []
    cc = cols.get("codigo")
    for r in rows[hr + 1:]:
        if cc is None or cc >= len(r):
            continue
        cod = r[cc]
        if not _es_codigo(cod):
            continue
        d = {"codigo": str(cod).strip(), "codigo_norm": norm_codigo(cod),
             "nombre": (r[cols["nombre"]] if cols.get("nombre") is not None and cols["nombre"] < len(r) else None)}
        for campo in CANON:
            j = cols.get(campo)
            d[campo] = _num(r[j]) if (j is not None and j < len(r)) else None
        out.append(d)
    return out, hr, cols


def leer_xlsx(path, hoja=None, perfil=None):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[hoja] if (hoja and hoja in wb.sheetnames) else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    return leer_filas(rows, perfil)


def leer_csv(contenido, perfil=None):
    import csv
    rows = list(csv.reader(io.StringIO(contenido.replace("\r\n", "\n"))))
    return leer_filas(rows, perfil)


def totales_por_clase(filas):
    """Suma saldo_final (o débito) por clase (primer dígito del PUC)."""
    tot = {}
    for f in filas:
        cn = f["codigo_norm"]
        if not cn:
            continue
        clase = cn[0]
        val = f.get("saldo_final")
        if val is None:
            val = f.get("debito") or 0.0
        tot[clase] = tot.get(clase, 0.0) + (val or 0.0)
    return tot
