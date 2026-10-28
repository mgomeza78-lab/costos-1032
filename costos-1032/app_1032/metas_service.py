# -*- coding: utf-8 -*-
"""Metas mixtas y evaluación del nivel de cumplimiento (Res. CRA 1032, Cap. 2).

Combina las metas REGULADAS (catálogo global por segmento, arts. 2.1.2.1.2.1/.2) con las
metas PROPIAS que define la empresa. Para las metas cuantitativas, el usuario ingresa el
valor REAL del indicador por año tarifario y el sistema EVALÚA el nivel de cumplimiento
(real vs objetivo, según el sentido ≥/≤/=). Las cualitativas (planes, buenas prácticas) se
evalúan por estado. En el período de inicio las metas solo se identifican/enuncian; la
evaluación cuantitativa aplica desde el año tarifario 1 (ver requisitos.metas_modo).
"""
from sqlalchemy import text

SENTIDOS = {"ge": "≥ objetivo (mayor es mejor)",
            "le": "≤ objetivo (menor es mejor)",
            "eq": "= objetivo"}


def evaluar(cuantitativa, objetivo_num, sentido, valor_real):
    """Devuelve (pct_cumplimiento|None, cumplido|None).

    pct es el nivel de cumplimiento 0..100 (se topa a 100); None si no es evaluable
    numéricamente (meta cualitativa, sin objetivo o sin valor real)."""
    if not cuantitativa or objetivo_num in (None, "") or valor_real in (None, ""):
        return None, None
    try:
        obj = float(objetivo_num); vr = float(valor_real)
    except (TypeError, ValueError):
        return None, None
    s = (sentido or "ge").strip()
    if s == "le":                       # menor es mejor (p. ej. pérdidas IPUF ≤ 4)
        ok = vr <= obj
        pct = 100.0 if vr <= obj else ((obj / vr * 100.0) if vr else 0.0)
    elif s == "eq":
        ok = abs(vr - obj) < 1e-9
        pct = 100.0 if ok else 0.0
    else:                               # 'ge': mayor es mejor (cobertura, continuidad…)
        ok = vr >= obj
        pct = (vr / obj * 100.0) if obj else None
    if pct is not None:
        pct = max(0.0, min(pct, 100.0))
    return pct, ok


def estado_auto(pct, ok):
    if ok:
        return "cumplido"
    if pct is None:
        return "pendiente"
    return "en_proceso"


def _seg_map(conn, empresa_id, origen, anio):
    """{ref_id: fila de seguimiento} para un origen y año."""
    rows = conn.execute(text(
        "SELECT ref_id, valor_real, estado, observacion FROM meta_seguimiento "
        "WHERE empresa_id=:e AND origen=:o AND anio_tarifario=:a"),
        {"e": empresa_id, "o": origen, "a": anio}).mappings().all()
    return {r["ref_id"]: dict(r) for r in rows}


def catalogo(conn, empresa_id, servicios, anio):
    """Metas reguladas (catálogo) con identificación (meta_empresa) y seguimiento del año `anio`,
    ya evaluadas. Cada fila trae cumplimiento_pct y cumplido para las cuantitativas."""
    cat = conn.execute(text(
        "SELECT c.id, c.codigo, c.servicio, c.objetivo, c.factor, c.nombre, c.tipo, "
        "       c.valor_estandar, c.articulo, c.cuantitativa, c.objetivo_num, c.unidad, c.sentido, "
        "       me.linea_base, me.meta_valor, me.anio_meta, me.estado AS estado_ident, me.observacion AS obs_ident "
        "FROM meta_catalogo c LEFT JOIN meta_empresa me ON me.meta_id=c.id AND me.empresa_id=:e "
        "WHERE c.servicio = ANY(:ss) ORDER BY c.orden"),
        {"e": empresa_id, "ss": servicios}).mappings().all()
    seg = _seg_map(conn, empresa_id, "regulacion", anio)
    return [_fila(dict(m), seg.get(m["id"]), "regulacion") for m in cat]


def propias(conn, empresa_id, servicios, anio):
    rows = conn.execute(text(
        "SELECT id, servicio, codigo, nombre, descripcion, cuantitativa, objetivo_num, unidad, sentido "
        "FROM meta_propia WHERE empresa_id=:e AND servicio = ANY(:ss) ORDER BY servicio, id"),
        {"e": empresa_id, "ss": servicios}).mappings().all()
    seg = _seg_map(conn, empresa_id, "propia", anio)
    out = []
    for m in rows:
        d = dict(m)
        d["objetivo"] = "Metas propias de la empresa"
        d["valor_estandar"] = _obj_txt(d)
        d["tipo"] = "propia"
        out.append(_fila(d, seg.get(m["id"]), "propia"))
    return out


def _obj_txt(d):
    if d.get("cuantitativa") and d.get("objetivo_num") is not None:
        sg = {"ge": "≥", "le": "≤", "eq": "="}.get(d.get("sentido") or "ge", "")
        return f"{sg} {_num(d['objetivo_num'])} {d.get('unidad') or ''}".strip()
    return d.get("descripcion") or "—"


def _num(x):
    try:
        f = float(x)
        return str(int(f)) if f == int(f) else f"{f:g}"
    except (TypeError, ValueError):
        return str(x)


def _fila(m, s, origen):
    s = s or {}
    vr = s.get("valor_real")
    pct, ok = evaluar(m.get("cuantitativa"), m.get("objetivo_num"), m.get("sentido"), vr)
    estado = s.get("estado") or (estado_auto(pct, ok) if vr is not None else "pendiente")
    m["origen"] = origen
    m["valor_real"] = vr
    m["cumplimiento_pct"] = pct
    m["cumplido"] = ok
    m["estado"] = estado
    m["obs_seg"] = s.get("observacion")
    return m


def seguimiento_set(conn, empresa_id, origen, ref_id, anio, valor_real, estado, observacion, usuario_id):
    if origen not in ("regulacion", "propia"):
        return "origen inválido"
    conn.execute(text(
        "INSERT INTO meta_seguimiento(empresa_id,origen,ref_id,anio_tarifario,valor_real,estado,"
        " observacion,actualizado_por) VALUES (:e,:o,:r,:a,:v,:es,:ob,:u) "
        "ON CONFLICT (empresa_id,origen,ref_id,anio_tarifario) DO UPDATE SET "
        " valor_real=excluded.valor_real, estado=excluded.estado, observacion=excluded.observacion, "
        " actualizado_por=excluded.actualizado_por, actualizado_en=now()"),
        {"e": empresa_id, "o": origen, "r": ref_id, "a": anio, "v": valor_real,
         "es": (estado or "").strip() or None, "ob": (observacion or "").strip() or None, "u": usuario_id})
    return None


def propia_add(conn, empresa_id, d, usuario_id):
    serv = (d.get("servicio") or "").strip()
    if serv not in ("acueducto", "alcantarillado"):
        return None, "servicio inválido"
    nombre = (d.get("nombre") or "").strip()
    if not nombre:
        return None, "el nombre de la meta es obligatorio"
    cuant = bool(d.get("objetivo_num") not in (None, ""))
    sentido = (d.get("sentido") or "ge").strip()
    if sentido not in SENTIDOS:
        sentido = "ge"
    pid = conn.execute(text(
        "INSERT INTO meta_propia(empresa_id,servicio,codigo,nombre,descripcion,cuantitativa,"
        " objetivo_num,unidad,sentido,creado_por) "
        "VALUES (:e,:s,:c,:n,:d,:q,:o,:u,:sg,:up) RETURNING id"),
        {"e": empresa_id, "s": serv, "c": (d.get("codigo") or "").strip() or None, "n": nombre,
         "d": (d.get("descripcion") or "").strip() or None, "q": cuant, "o": d.get("objetivo_num"),
         "u": (d.get("unidad") or "").strip() or None, "sg": sentido, "up": usuario_id}).scalar()
    return pid, None


def propia_eliminar(conn, empresa_id, pid):
    conn.execute(text("DELETE FROM meta_propia WHERE empresa_id=:e AND id=:i"), {"e": empresa_id, "i": pid})
    conn.execute(text("DELETE FROM meta_seguimiento WHERE empresa_id=:e AND origen='propia' AND ref_id=:i"),
                 {"e": empresa_id, "i": pid})


def resumen_cumplimiento(filas):
    """Conteos para el encabezado: evaluadas, cumplidas, en proceso."""
    evaluadas = [f for f in filas if f.get("valor_real") is not None]
    cumplidas = [f for f in evaluadas if f.get("cumplido")]
    return {"n_total": len(filas), "n_evaluadas": len(evaluadas), "n_cumplidas": len(cumplidas)}
