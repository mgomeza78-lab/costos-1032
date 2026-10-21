# -*- coding: utf-8 -*-
"""Área de Prestación del Servicio — APS (art. 2.1.2.1.1.5, Res. CRA 1032 de 2026).

La metodología establece UN APS por cada municipio/distrito atendido. Este
módulo gestiona, por empresa, la configuración del APS de cada municipio (los
municipios vienen de `empresa_municipio`, migración 010), los soportes
documentales por APS (mapa georreferenciado, instrumento de ordenamiento, Plan
Maestro, reporte al municipio…) y una validación de completitud de la
información que la 1032 exige para el período de inicio.

No calcula costos: la configuración del APS es el primer paso del estudio y
alimenta la segmentación, las metas (que en el período de inicio solo se
identifican) y, en el primer recálculo, el reparto territorial.
"""
from sqlalchemy import text

# ---- Catálogos (etiquetas para la interfaz) ----
SERVICIOS = {"ac": "Solo acueducto", "al": "Solo alcantarillado", "ambos": "Acueducto y alcantarillado"}
ZONAS = {"urbana": "Solo urbana", "urbana_rural": "Urbana y rural"}
SISTEMA_RURAL = {
    "na": "No aplica (sin zona rural)",
    "integrado": "Integrado a la zona urbana",
    "no_integrado_urbana": "No integrado a la zona urbana",
    "no_integrado_urbano_rural": "No integrado con sistema urbano-rural",
}
INTERCONEXION = {
    "na": "No aplica (un solo municipio)",
    "interconectado": "Sistema interconectado",
    "no_interconectado": "Sistema no interconectado",
    "mixto": "Mixto (interconectado y no interconectado)",
}
TIPO_REGIONAL = {
    "na": "No aplica",
    "mercado_regional": "Mercado regional declarado",
    "costos_unificados": "Esquema regional con costos unificados",
    "no_unificados": "Esquema regional sin costos unificados",
}
INSTRUMENTOS_OT = {"POT": "POT", "PBOT": "PBOT", "EOT": "EOT"}
CATEGORIAS_ARCHIVO = {
    "georreferenciacion": "Georreferenciación (mapa, polígono y coordenadas)",
    "pot_pbot_eot": "Instrumento de ordenamiento (POT/PBOT/EOT)",
    "pmaa": "Plan Maestro de Acueducto y Alcantarillado",
    "reporte_municipio": "Reporte del APS al municipio/distrito",
    "soporte_825": "Soporte de aplicación de la Res. CRA 825 / mercado regional",
    "soporte_general": "Otro soporte",
}
# Formatos admitidos para los soportes (Excel/CSV/PDF e imágenes/archivos geográficos del polígono)
EXT_PERMITIDAS = {"pdf", "xlsx", "xls", "xlsm", "csv", "png", "jpg", "jpeg",
                  "kml", "kmz", "zip", "geojson", "json", "dwg", "shp"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB por archivo

# Columnas editables del APS (para el upsert desde el formulario)
_BOOL = ("aps_difiere_servicios", "esquema_regional", "mercado_regional_declarado",
         "aplicaba_825", "menor_5000", "pdet", "zomac", "ed_particular",
         "ed_urbano_zdu", "ed_rural_zrni", "toma_posesion_sspd",
         "georref_presentada", "pmaa", "reportado_municipio")
_TEXTO = ("nombre", "codigo_aps", "servicios", "zona", "sistema_rural",
          "sistema_interconexion", "tipo_regional", "georref_sistema",
          "instrumento_ot", "instrumento_ot_acto", "reportado_acto", "observacion")
# Valores por defecto de las columnas de texto NOT NULL (evitan nulos en el upsert)
_DEF_TEXTO = {"servicios": "ambos", "zona": "urbana", "sistema_rural": "na",
              "sistema_interconexion": "na", "tipo_regional": "na",
              "georref_sistema": "MAGNA-SIRGAS"}


def municipios_empresa(conn, empresa_id):
    """Municipios atendidos por la empresa (base de los APS)."""
    return conn.execute(text(
        "SELECT m.cod_dane, m.nombre AS municipio, d.nombre AS departamento "
        "FROM empresa_municipio em JOIN municipio m ON m.cod_dane = em.cod_dane "
        "JOIN departamento d ON d.cod_dane = m.cod_dpto "
        "WHERE em.empresa_id = :e ORDER BY d.nombre, m.nombre"),
        {"e": empresa_id}).mappings().all()


def _row_aps(conn, empresa_id, cod_dane):
    return conn.execute(text(
        "SELECT * FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
        {"e": empresa_id, "c": cod_dane}).mappings().first()


def obtener(conn, empresa_id, cod_dane):
    return _row_aps(conn, empresa_id, cod_dane)


def lista(conn, empresa_id):
    """Un elemento por municipio de la empresa, con su APS (si existe) y el
    número de soportes cargados. Incluye municipios aún sin APS configurado."""
    munis = municipios_empresa(conn, empresa_id)
    conteos = dict(conn.execute(text(
        "SELECT aps_id, count(*) FROM aps_archivo WHERE empresa_id=:e GROUP BY aps_id"),
        {"e": empresa_id}).all())
    out = []
    for m in munis:
        row = _row_aps(conn, empresa_id, m["cod_dane"])
        out.append({
            "cod_dane": m["cod_dane"], "municipio": m["municipio"],
            "departamento": m["departamento"],
            "aps": dict(row) if row else None,
            "n_archivos": conteos.get(row["id"], 0) if row else 0,
            "faltantes": validaciones(dict(row)) if row else ["APS sin configurar"],
            "condicion_especial": condicion_especial(dict(row)) if row else [],
        })
    return out


def guardar(conn, empresa_id, cod_dane, d, usuario_id):
    """Crea o actualiza (upsert) el APS de un municipio. `d` es un dict de campos
    ya tipados (bool/num/texto). Devuelve (aps_id, None) o (None, error)."""
    cod_dane = (cod_dane or "").strip()
    ok_mun = conn.execute(text(
        "SELECT 1 FROM empresa_municipio WHERE empresa_id=:e AND cod_dane=:c"),
        {"e": empresa_id, "c": cod_dane}).first()
    if not ok_mun:
        return None, "el municipio no está entre los atendidos por la empresa"
    campos = {k: bool(d.get(k)) for k in _BOOL}        # los NOT NULL booleanos nunca quedan en NULL
    for k in _TEXTO:
        v = d.get(k)
        campos[k] = _DEF_TEXTO.get(k) if (v is None or v == "") else v
    campos.update({
        "numero_aps": d.get("numero_aps"),
        "area_ha": d.get("area_ha"),
        "reportado_fecha": d.get("reportado_fecha"),
        "empresa_id": empresa_id, "cod_dane": cod_dane, "u": usuario_id,
    })
    cols = list(_BOOL + _TEXTO) + ["numero_aps", "area_ha", "reportado_fecha"]
    set_sql = ", ".join(f"{c}=excluded.{c}" for c in cols)
    ins_cols = ", ".join(cols)
    ins_vals = ", ".join(f":{c}" for c in cols)
    aps_id = conn.execute(text(
        f"INSERT INTO aps (empresa_id, cod_dane, {ins_cols}, actualizado_por) "
        f"VALUES (:empresa_id, :cod_dane, {ins_vals}, :u) "
        f"ON CONFLICT (empresa_id, cod_dane) DO UPDATE SET {set_sql}, "
        f" actualizado_por=excluded.actualizado_por, actualizado_en=now() "
        f"RETURNING id"), campos).scalar()
    return aps_id, None


def condicion_especial(row):
    """Condiciones especiales aplicables al APS (art. 2.1.2.1.1.5 y la condición
    especial del subtítulo). Devuelve la lista de etiquetas que apliquen."""
    if not row:
        return []
    c = []
    if row.get("ed_rural_zrni"):
        c.append("Zona rural con sistema no integrado (ZRNI)")
    if row.get("ed_urbano_zdu"):
        c.append("Esquema diferencial urbano (ZDU, área de difícil gestión)")
    if row.get("ed_particular"):
        c.append("Esquema diferencial de prestación en condición particular")
    if row.get("menor_5000") or row.get("pdet") or row.get("zomac"):
        et = []
        if row.get("menor_5000"):
            et.append("≤ 5.000 suscriptores")
        if row.get("pdet"):
            et.append("PDET")
        if row.get("zomac"):
            et.append("ZOMAC")
        c.append("APS de menor tamaño / " + ", ".join(et))
    if row.get("toma_posesion_sspd"):
        c.append("Persona prestadora en toma de posesión por la SSPD")
    return c


def validaciones(row):
    """Información mínima pendiente del APS para el período de inicio. Devuelve la
    lista de faltantes; vacía = completa. (art. 2.1.2.1.1.5)"""
    if not row:
        return ["APS sin configurar"]
    f = []
    if not row.get("servicios"):
        f.append("Servicios prestados")
    if not row.get("zona"):
        f.append("Zonas de prestación")
    if row.get("zona") == "urbana_rural" and row.get("sistema_rural") in (None, "na"):
        f.append("Tipo de sistema rural (integrado / no integrado)")
    if row.get("esquema_regional"):
        if row.get("sistema_interconexion") in (None, "na"):
            f.append("Interconexión del esquema regional")
        if row.get("tipo_regional") in (None, "na"):
            f.append("Tipo de esquema regional (mercado/costos unificados)")
    if not row.get("georref_presentada"):
        f.append("Georreferenciación (mapa, polígono y coordenadas)")
    if not row.get("instrumento_ot"):
        f.append("Instrumento de ordenamiento (POT/PBOT/EOT)")
    if not row.get("reportado_municipio"):
        f.append("Reporte del APS al municipio")
    return f


def resumen(conn, empresa_id):
    """Estado de la configuración de APS de la empresa (completitud)."""
    items = lista(conn, empresa_id)
    n_mun = len(items)
    conf = [i for i in items if i["aps"]]
    completos = [i for i in conf if not i["faltantes"]]
    n_aps_decl = conn.execute(text("SELECT n_aps FROM empresa WHERE id=:e"),
                              {"e": empresa_id}).scalar()
    return {
        "n_municipios": n_mun,
        "n_configurados": len(conf),
        "n_completos": len(completos),
        "n_pendientes": n_mun - len(completos),
        "n_aps_declarado": n_aps_decl,
        "coincide_declarado": (n_aps_decl is None) or (n_aps_decl == n_mun),
        "items": items,
    }


# ---------------- Soportes documentales ----------------
def archivos(conn, empresa_id, aps_id):
    """Metadatos de los soportes de un APS (sin el contenido)."""
    return conn.execute(text(
        "SELECT id, categoria, nombre, tipo, tamano, subido_en "
        "FROM aps_archivo WHERE empresa_id=:e AND aps_id=:a "
        "ORDER BY categoria, subido_en DESC"),
        {"e": empresa_id, "a": aps_id}).mappings().all()


def guardar_archivo(conn, empresa_id, aps_id, categoria, nombre, tipo, contenido, usuario_id):
    conn.execute(text(
        "INSERT INTO aps_archivo (empresa_id, aps_id, categoria, nombre, tipo, tamano, contenido, subido_por) "
        "VALUES (:e,:a,:c,:n,:t,:z,:b,:u)"),
        {"e": empresa_id, "a": aps_id, "c": categoria, "n": nombre, "t": tipo,
         "z": len(contenido or b""), "b": contenido, "u": usuario_id})


def archivo(conn, empresa_id, archivo_id):
    """Un soporte con su contenido, para descarga."""
    return conn.execute(text(
        "SELECT nombre, tipo, contenido FROM aps_archivo WHERE empresa_id=:e AND id=:i"),
        {"e": empresa_id, "i": archivo_id}).mappings().first()


def eliminar_archivo(conn, empresa_id, archivo_id):
    conn.execute(text("DELETE FROM aps_archivo WHERE empresa_id=:e AND id=:i"),
                 {"e": empresa_id, "i": archivo_id})
