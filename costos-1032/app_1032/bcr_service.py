# -*- coding: utf-8 -*-
"""Base de Capital Regulada (BCR) y proyección indicativa del CMI (Res. CRA 1032).

Inventario de activos de la BCR por los tres componentes del art. 2.1.2.1.3.5.18
(1-infraestructura, 2-inversiones ambientales y de gestión del riesgo,
3-activos administrativos y operativos). En el período de inicio la BCR del año
tarifario i-1 es la BCR₀ (art. 2.1.2.1.3.5, par. 1), calculada según el marco
anterior de cada APS (Res. 688 → art. 2.1.2.1.3.5.4; Res. 825 → art. 2.1.2.1.3.5.7).

La proyección del CMI combina el CMI_BCR (remuneración de la BCR a la tasa r más la
cuota anual de recuperación del capital, arts. 2.1.2.1.3.5.10 y .11) con el CMI_POIR
de los proyectos del POIR que entran en operación (art. 2.1.2.1.3.5.14). Es una
**proyección indicativa** con supuestos explícitos; la cuantificación normativa
activo-por-activo corresponde al recálculo anual.
"""
from datetime import date
from sqlalchemy import text
import poir_cmi_service as poir

COMPONENTES = {1: "Infraestructura",
               2: "Inversiones ambientales y de gestión del riesgo",
               3: "Activos administrativos y operativos"}
SERVICIOS = {"acueducto": "Acueducto", "alcantarillado": "Alcantarillado"}


# ---------------- Inventario de activos ----------------
def lista(conn, empresa_id, servicio=None):
    sql = ("SELECT id, servicio, componente, nombre, codigo, cod_dane, valor_bruto, plazo_remanente, "
           "       cuota_anual, valor_pendiente, origen, observacion, tipo_activo, vida_util, "
           "       via688, vp_cmi_q, vpr0, va0, anio_poir, ejecucion_real, fecha_operacion "
           "FROM bcr_activo WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " ORDER BY servicio, componente, nombre"
    return conn.execute(text(sql), p).mappings().all()


def guardar(conn, empresa_id, d, usuario_id):
    serv = (d.get("servicio") or "").strip()
    if serv not in SERVICIOS:
        return None, "servicio inválido"
    try:
        comp = int(d.get("componente"))
    except (TypeError, ValueError):
        return None, "componente inválido"
    if comp not in COMPONENTES:
        return None, "componente inválido"
    nombre = (d.get("nombre") or "").strip()
    if not nombre:
        return None, "el nombre del activo es obligatorio"
    # VA₀: si el usuario no lo da pero da VPR₀, se calcula con los parámetros 688 del servicio.
    va0 = d.get("va0")
    vpr0 = d.get("vpr0")
    if va0 is None and vpr0 is not None:
        p = param_get(conn, empresa_id, serv)
        if p and p["r688"] is not None and p["fecha_inicio_688"] and _fa0(p) is not None:
            va0 = float(vpr0) * ((1 + float(p["r688"])) ** _t_anios(p["fecha_inicio_688"])) * _fa0(p)
    vp = d.get("valor_pendiente")
    if vp is None and va0 is not None:
        vp = va0                       # el valor pendiente que integra la BCR (antes de compensar)
    campos = {"e": empresa_id, "s": serv, "c": comp, "n": nombre,
              "cd": (d.get("cod_dane") or "").strip() or None,
              "vb": d.get("valor_bruto"), "pr": d.get("plazo_remanente"),
              "ca": d.get("cuota_anual"), "vp": vp,
              "og": (d.get("origen") or "BCR0").strip(),
              "ob": (d.get("observacion") or "").strip() or None,
              "ta": (d.get("tipo_activo") or "").strip() or None, "vu": d.get("vida_util"),
              "via": d.get("via688"), "vpcq": d.get("vp_cmi_q"), "vpr": vpr0, "va0": va0,
              "ap": d.get("anio_poir"), "er": d.get("ejecucion_real"),
              "fo": (d.get("fecha_operacion") or None),
              "codg": (d.get("codigo") or "").strip() or None, "u": usuario_id}
    aid = d.get("id")
    if aid:
        conn.execute(text(
            "UPDATE bcr_activo SET servicio=:s, componente=:c, nombre=:n, cod_dane=:cd, "
            " valor_bruto=:vb, plazo_remanente=:pr, cuota_anual=:ca, valor_pendiente=:vp, "
            " origen=:og, observacion=:ob, tipo_activo=:ta, vida_util=:vu, via688=:via, "
            " vp_cmi_q=:vpcq, vpr0=:vpr, va0=:va0, anio_poir=:ap, ejecucion_real=:er, "
            " fecha_operacion=:fo, codigo=:codg, actualizado_en=now() WHERE empresa_id=:e AND id=:i"),
            {**campos, "i": aid})
        return aid, None
    aid = conn.execute(text(
        "INSERT INTO bcr_activo(empresa_id,servicio,componente,nombre,cod_dane,valor_bruto,"
        " plazo_remanente,cuota_anual,valor_pendiente,origen,observacion,tipo_activo,vida_util,"
        " via688,vp_cmi_q,vpr0,va0,anio_poir,ejecucion_real,fecha_operacion,codigo,cargado_por) "
        "VALUES (:e,:s,:c,:n,:cd,:vb,:pr,:ca,:vp,:og,:ob,:ta,:vu,:via,:vpcq,:vpr,:va0,:ap,:er,:fo,:codg,:u) "
        "RETURNING id"), campos).scalar()
    return aid, None


# ---------------- Carga masiva de activos de la BCR₀ (CSV / Excel) ----------------
# Columnas del archivo (una fila por activo). Alias aceptados entre paréntesis.
COLS_ACTIVO = ["codigo", "nombre", "servicio", "componente", "origen", "tipo_activo",
               "via688", "vpr0", "va0", "prr", "cak", "anio_poir", "ejecucion_real",
               "fecha_operacion", "observacion"]
_ALIAS = {"prr": "plazo_remanente", "cak": "cuota_anual", "vida_util": "vida_util"}


def _num_x(x):
    if x is None:
        return None
    s = str(x).strip().replace("$", "").replace(" ", "")
    if s == "":
        return None
    # admite 1.234.567,89 (es-CO), 1,234,567.89 (US), 1234567.89 y 30.000.000.000 (puntos de miles)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):   # la coma es el último separador = decimal (es-CO)
            s = s.replace(".", "").replace(",", ".")
        else:                             # el punto es el último = decimal (US)
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:               # varios puntos = separadores de miles
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def leer_archivo_activos(raw, filename=""):
    """Devuelve (filas, error). Lee CSV o Excel con las columnas de COLS_ACTIVO."""
    import io as _io
    fn = (filename or "").lower()
    rows = []
    try:
        if fn.endswith((".xlsx", ".xlsm", ".xls")):
            import openpyxl
            wb = openpyxl.load_workbook(_io.BytesIO(raw), data_only=True, read_only=True)
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            hdr = next(it, None)
            if not hdr:
                return [], "el archivo está vacío"
            cols = [str(h).strip().lower() if h is not None else "" for h in hdr]
            for vals in it:
                if vals is None or all(v is None or str(v).strip() == "" for v in vals):
                    continue
                rows.append({cols[i]: vals[i] for i in range(min(len(cols), len(vals)))})
            wb.close()
        else:
            import csv as _csv
            txt = raw.decode("utf-8-sig", "ignore") if isinstance(raw, bytes) else raw
            rows = list(_csv.DictReader(_io.StringIO(txt.replace("\r\n", "\n"))))
            rows = [{(k or "").strip().lower(): v for k, v in r.items()} for r in rows]
    except Exception as ex:
        return [], f"no se pudo leer el archivo ({type(ex).__name__})"
    if not rows:
        return [], "el archivo no tiene filas de datos"
    faltan = {"nombre", "servicio", "componente"} - set(rows[0].keys())
    if faltan:
        return [], f"faltan columnas obligatorias: {', '.join(sorted(faltan))}"
    return rows, None


def ingesta_activos(conn, empresa_id, filas, usuario_id):
    """Upsert masivo por (empresa, servicio, codigo). Devuelve (ok, errores)."""
    ok, err = 0, []
    for i, r in enumerate(filas, start=2):
        serv = _SERV_IN.get(str(r.get("servicio") or "").strip().lower())
        d = {
            "codigo": (str(r.get("codigo") or "").strip() or None),
            "nombre": str(r.get("nombre") or "").strip(),
            "servicio": serv or (r.get("servicio") or ""),
            "componente": r.get("componente"),
            "origen": (str(r.get("origen") or "").strip() or "BCR0"),
            "tipo_activo": (str(r.get("tipo_activo") or "").strip() or None),
            "via688": _num_x(r.get("via688")), "vpr0": _num_x(r.get("vpr0")),
            "va0": _num_x(r.get("va0")), "vp_cmi_q": _num_x(r.get("vp_cmi_q")),
            "plazo_remanente": _num_x(r.get("prr") if r.get("prr") is not None else r.get("plazo_remanente")),
            "cuota_anual": _num_x(r.get("cak") if r.get("cak") is not None else r.get("cuota_anual")),
            "vida_util": _num_x(r.get("vida_util")), "ejecucion_real": _num_x(r.get("ejecucion_real")),
            "observacion": (str(r.get("observacion") or "").strip() or None),
        }
        ap = str(r.get("anio_poir") or "").strip()
        d["anio_poir"] = int(float(ap)) if ap.replace(".", "").isdigit() else None
        fo = str(r.get("fecha_operacion") or "").strip()
        d["fecha_operacion"] = fo[:10] if fo and fo[:4].isdigit() else None
        if d["codigo"] and serv:
            ex = conn.execute(text("SELECT id FROM bcr_activo WHERE empresa_id=:e AND servicio=:s AND codigo=:c"),
                              {"e": empresa_id, "s": serv, "c": d["codigo"]}).scalar()
            if ex:
                d["id"] = ex
        _aid, e = guardar(conn, empresa_id, d, usuario_id)
        if e:
            err.append(f"fila {i}: {e}")
        else:
            ok += 1
    return ok, err


_SERV_IN = {"ac": "acueducto", "acueducto": "acueducto",
            "al": "alcantarillado", "alcantarillado": "alcantarillado"}


def plantilla_activos_bytes():
    """Plantilla Excel para la carga masiva de los activos de la BCR₀ de inicio (688)."""
    import io as _io
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Activos_BCR0"
    ws.append(COLS_ACTIVO)
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.append(["AC-001", "Red matriz sector norte", "acueducto", 1, "VI287", "red",
               41200000000, 9800000000, "", 22, "", "", "", "", "heredado 287"])
    ws.append(["AC-POIR-012", "Ampliación conducción", "acueducto", 1, "POIR688", "conducción",
               "", "", "", 40, "", 5, 300000000, "2021-03-01", "proyecto POIR"])
    ws.append(["AL-AO-003", "Equipos administrativos", "alcantarillado", 3, "VI_AO", "admin",
               800000000, 650000000, "", 10, "", "", "", "", "activo admin/operativo"])
    nota = wb.create_sheet("INSTRUCCIONES")
    txt = [
        "Una fila por activo que entró al inicio de la 688. Columnas:",
        "codigo: identificador del activo (para poder actualizarlo después). Opcional pero recomendado.",
        "nombre: descripción del activo (OBLIGATORIO).",
        "servicio: acueducto o alcantarillado (acepta AC / AL) (OBLIGATORIO).",
        "componente: 1 infraestructura · 2 ambiental/riesgo · 3 admin/operativos (OBLIGATORIO).",
        "origen: VI287 · VIdif287 · POIR688 · VIDIF_688 · VI_IAR · VI_AO · TERRENO.",
        "via688: valor de inversión del activo en pesos de diciembre de 2014.",
        "vpr0: valor pendiente por recuperar ($2014). Si lo cargas, el VA₀ se calcula solo (VPR₀·(1+r688)^t·fa0).",
        "va0: valor actualizado ($dic-2025). Opcional; si no, se deriva del VPR₀.",
        "prr: plazo de recuperación remanente (años).  cak: cuota anual de capital ($).",
        "anio_poir / ejecucion_real / fecha_operacion: solo para activos del POIR (VIA=ejecucion/(1+r688)^anio).",
        "El r688, los IPC (fa0), el CCP y la fecha de inicio 688 ya se derivan automáticamente en el sistema.",
        "Puedes subir varios archivos a la vez. El sistema actualiza por (servicio + codigo) si el activo ya existe.",
    ]
    for i, t in enumerate(txt, 1):
        nota[f"A{i}"] = t
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- Parámetros 688 y series (agua facturada / CMI cobrado) ----------------
def _t_anios(fecha_inicio_688):
    """Años de aplicación de la 688 hasta el 30-jun-2026 (meses/12)."""
    if not fecha_inicio_688:
        return 0.0
    y, m = fecha_inicio_688.year, fecha_inicio_688.month
    meses = (2026 - y) * 12 + (6 - m)
    return max(meses, 0) / 12.0


def _fa0(p):
    """Factor de actualización = IPC dic-2025 / IPC dic-2014."""
    if not p:
        return None
    i14, i25 = p["ipc_dic_2014"], p["ipc_dic_2025"]
    if i14 and i25:
        return float(i25) / float(i14)
    return None


# WACC de la Resolución CRA 688 de 2014 por segmento de la 688 (dos segmentos):
#   · Segmento 1 — Grandes prestadores con más de 100.000 suscriptores → 12,28 %.
#   · Segmento 2 — Prestadores con 5.001–100.000 suscriptores        → 12,76 %.
R688_SEG = {1: 0.1228, 2: 0.1276}
IPUF_INICIO = 6.0   # IPUF* estándar del período de inicio (art. 2.1.2.1.3.5.2, par. 1): 6 m³/susc·mes


def segmento_688(suscriptores):
    """Segmento de la Res. 688 por número de suscriptores: 1 (>100.000), 2 (5.001–100.000)."""
    if suscriptores is None:
        return None
    n = int(suscriptores)
    if n > 100000:
        return 1
    if n > 5000:
        return 2
    return None


def r688_de_segmento(seg):
    return R688_SEG.get(seg)


def ipc_dic(conn, anio):
    """IPC de diciembre de un año desde la tabla de IPC (indice_ipc, mes 12), o None."""
    return conn.execute(text("SELECT indice FROM indice_ipc WHERE anio=:a AND mes=12 ORDER BY 1 LIMIT 1"),
                        {"a": anio}).scalar()


def ccp_desde_consumos(conn, empresa_id, servicio, anio=2025, ipuf=IPUF_INICIO):
    """CCP del año (art. 2.1.2.1.3.3.1), SIN tope: CCP = (ISUF − IPUF*)·N = AP − IPUF*·N.
    AP = Σ m³ producidos (macromedición) del año. IPUF* = 6 m³/susc·mes en el período de inicio.
    En alcantarillado (sin macromedición propia) el IPUF real se estima con el del acueducto del
    mismo año. Si no hay forma de estimar las pérdidas, CCP = AF (sin corrección). None si no hay
    información comercial."""
    row = conn.execute(text(
        "SELECT coalesce(sum(m3_facturados),0) AS m3, coalesce(sum(suscriptores),0) AS susc, count(*) AS n "
        "FROM carga_mensual WHERE empresa_id=:e AND servicio=:s AND anio=:a AND cod_dane='' AND m3_facturados IS NOT NULL"),
        {"e": empresa_id, "s": servicio, "a": anio}).mappings().first()
    if not row or not row["n"] or not row["susc"]:
        return None
    af = float(row["m3"]); n = float(row["susc"])
    ap = float(conn.execute(text(
        "SELECT coalesce(sum(m3_producido),0) FROM macromedicion WHERE empresa_id=:e AND servicio=:s AND anio=:a"),
        {"e": empresa_id, "s": servicio, "a": anio}).scalar() or 0.0)
    if ap > 0:
        return ap - float(ipuf) * n
    # Sin AP propio (alcantarillado): estima el IPUF real con el del acueducto del año base.
    ac = conn.execute(text(
        "SELECT coalesce(sum(m3_facturados),0) AS af, coalesce(sum(suscriptores),0) AS susc "
        "FROM carga_mensual WHERE empresa_id=:e AND servicio='acueducto' AND anio=:a AND cod_dane='' "
        "AND m3_facturados IS NOT NULL"), {"e": empresa_id, "a": anio}).mappings().first()
    ap_ac = float(conn.execute(text(
        "SELECT coalesce(sum(m3_producido),0) FROM macromedicion WHERE empresa_id=:e AND servicio='acueducto' AND anio=:a"),
        {"e": empresa_id, "a": anio}).scalar() or 0.0)
    if ac and ac["susc"] and ap_ac > 0:
        ipuf_real_ac = (ap_ac - float(ac["af"])) / float(ac["susc"])
        return af + (ipuf_real_ac - float(ipuf)) * n
    return af


def param_get(conn, empresa_id, servicio):
    return conn.execute(text("SELECT * FROM bcr_param WHERE empresa_id=:e AND servicio=:s"),
                        {"e": empresa_id, "s": servicio}).mappings().first()


def params(conn, empresa_id):
    return {p["servicio"]: p for p in conn.execute(text(
        "SELECT * FROM bcr_param WHERE empresa_id=:e"), {"e": empresa_id}).mappings().all()}


def param_set(conn, empresa_id, servicio, d):
    if servicio not in SERVICIOS:
        return False, "servicio inválido"
    conn.execute(text(
        "INSERT INTO bcr_param(empresa_id,servicio,r688,ipc_dic_2014,ipc_dic_2025,fecha_inicio_688,"
        " provision_poir,ccp_2025,observacion) VALUES (:e,:s,:r,:i14,:i25,:f,:pv,:ccp,:ob) "
        "ON CONFLICT (empresa_id,servicio) DO UPDATE SET "
        " r688=COALESCE(excluded.r688, bcr_param.r688), "
        " ipc_dic_2014=COALESCE(excluded.ipc_dic_2014, bcr_param.ipc_dic_2014), "
        " ipc_dic_2025=COALESCE(excluded.ipc_dic_2025, bcr_param.ipc_dic_2025), "
        " fecha_inicio_688=COALESCE(excluded.fecha_inicio_688, bcr_param.fecha_inicio_688), "
        " provision_poir=COALESCE(excluded.provision_poir, bcr_param.provision_poir), "
        " ccp_2025=COALESCE(excluded.ccp_2025, bcr_param.ccp_2025), "
        " observacion=COALESCE(excluded.observacion, bcr_param.observacion), actualizado_en=now()"),
        {"e": empresa_id, "s": servicio, "r": d.get("r688"), "i14": d.get("ipc_dic_2014"),
         "i25": d.get("ipc_dic_2025"), "f": d.get("fecha_inicio_688") or None,
         "pv": d.get("provision_poir"), "ccp": d.get("ccp_2025"),
         "ob": (d.get("observacion") or "").strip() or None})
    return True, None


def serie_list(conn, empresa_id, servicio=None):
    sql = ("SELECT servicio, anio_tarifario, mes, q_m3, cmi_cobrado, segmento FROM bcr_serie WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " ORDER BY servicio, anio_tarifario, mes"
    return conn.execute(text(sql), p).mappings().all()


def serie_set(conn, empresa_id, servicio, anio_tarifario, q_m3, cmi_cobrado, segmento=None, mes=0):
    if servicio not in SERVICIOS:
        return False, "servicio inválido"
    conn.execute(text(
        "INSERT INTO bcr_serie(empresa_id,servicio,anio_tarifario,mes,q_m3,cmi_cobrado,segmento) "
        "VALUES (:e,:s,:a,:m,:q,:c,:g) ON CONFLICT (empresa_id,servicio,anio_tarifario,mes) DO UPDATE SET "
        " q_m3=excluded.q_m3, cmi_cobrado=excluded.cmi_cobrado, segmento=excluded.segmento"),
        {"e": empresa_id, "s": servicio, "a": anio_tarifario, "m": int(mes or 0),
         "q": q_m3, "c": cmi_cobrado, "g": segmento})
    return True, None


def serie_del(conn, empresa_id, servicio, anio_tarifario, mes=None):
    sql = "DELETE FROM bcr_serie WHERE empresa_id=:e AND servicio=:s AND anio_tarifario=:a"
    p = {"e": empresa_id, "s": servicio, "a": anio_tarifario}
    if mes is not None:
        sql += " AND mes=:m"; p["m"] = int(mes)
    conn.execute(text(sql), p)


def cargar_serie_csv(conn, empresa_id, contenido):
    """Cargue masivo de la serie de agua facturada de la 688 (una fila por año y servicio).
    Columnas: servicio, anio (1-10), agua_facturada (m³), cmi_cobrado ($/m³), segmento (1|2, opcional).
    Tolera encabezados en mayúsculas, separador coma o ';' y alias de columnas. Devuelve (ok, errores)."""
    import ingesta as _ing
    rows = _ing._rows(contenido)
    if not rows:
        return 0, ["el archivo está vacío o sin encabezado"]
    cols = set(h for h in rows[0].keys() if h)
    A_ANIO = ("anio", "anio_tarifario", "año", "ano", "anio_688", "año_688")
    A_MES = ("mes", "month")
    A_Q = ("agua_facturada", "agua_facturada_m3", "q_m3", "q", "m3")
    faltan = []
    if "servicio" not in cols:
        faltan.append("servicio")
    if not (cols & set(A_ANIO)):
        faltan.append("anio")
    if not (cols & set(A_MES)):
        faltan.append("mes")
    if not (cols & set(A_Q)):
        faltan.append("agua_facturada")
    if faltan:
        return 0, ["faltan columnas: " + ", ".join(faltan)]

    def _col(r, *names):
        for n in names:
            if n in r and (r.get(n) or "").strip() != "":
                return r.get(n)
        return None

    ok, err = 0, []
    for i, r in enumerate(rows, 2):
        serv = _ing._norm_serv(_col(r, "servicio"))
        if not serv:
            err.append(f"fila {i}: servicio inválido '{_col(r, 'servicio')}'")
            continue
        anio = _ing._int(_col(r, *A_ANIO))
        if not anio or not (1 <= anio <= 10):
            err.append(f"fila {i}: año de la 688 inválido (debe ser 1–10)")
            continue
        mes = _ing._mes_cell(_col(r, *A_MES))
        if not mes or not (1 <= mes <= 12):
            err.append(f"fila {i}: mes inválido '{_col(r, *A_MES)}' (debe ser 1–12 o nombre)")
            continue
        q = _ing._num(_col(r, *A_Q))
        cmi = _ing._num(_col(r, "cmi_cobrado", "cmi", "cmi688", "cmi_688"))
        seg = _ing._int(_col(r, "segmento", "segmento688", "segmento_688", "seg"))
        if seg not in (1, 2):
            seg = None
        try:
            with conn.begin_nested():
                serie_set(conn, empresa_id, serv, anio, q, cmi, seg, mes=mes)
            ok += 1
        except Exception as ex:
            err.append(f"fila {i}: {type(ex).__name__}")
    return ok, err


def ingresos_vp(conn, empresa_id, servicio):
    """VP de los ingresos recuperados vía CMI = Σ CMI688ᵢ·Qᵢ/(1+r688)^i.

    Es el término VP(CMI688×Q) del VPR₀ (art. 2.1.2.1.3.5.5). Devuelve el detalle
    año a año (ingreso = CMI·Q, factor de descuento, VP del año) y el total, a
    partir de las series de agua facturada y CMI cobrado de la 688.
    """
    p = param_get(conn, empresa_id, servicio)
    r = float(p["r688"]) if p and p["r688"] is not None else None
    if r is None:                                 # el r688 lo da el segmento de la 688
        susc = conn.execute(text("SELECT suscriptores_seg FROM empresa WHERE id=:e"),
                            {"e": empresa_id}).scalar()
        r = r688_de_segmento(segmento_688(susc))
    # Serie mensual: por cada año i el ingreso = Σ_mes (CMI688×Q); VP_i = ingreso_i/(1+r)^i.
    por_anio, meses = {}, []
    for s in serie_list(conn, empresa_id, servicio):
        i = int(s["anio_tarifario"]); mes = int(s["mes"] or 0)
        q = float(s["q_m3"]) if s["q_m3"] is not None else None
        cmi = float(s["cmi_cobrado"]) if s["cmi_cobrado"] is not None else None
        ingreso = (cmi * q) if (q is not None and cmi is not None) else None
        d = por_anio.setdefault(i, {"ingreso": 0.0, "n": 0})
        if ingreso is not None:
            d["ingreso"] += ingreso; d["n"] += 1
        meses.append({"anio": i, "mes": mes, "q": q, "cmi": cmi, "ingreso": ingreso})
    filas, total = [], 0.0
    for i in sorted(por_anio):
        ingreso_i = por_anio[i]["ingreso"] if por_anio[i]["n"] else None
        factor = (1.0 / ((1 + r) ** i)) if r is not None else None
        vp = (ingreso_i * factor) if (ingreso_i is not None and factor is not None) else None
        if vp is not None:
            total += vp
        filas.append({"anio": i, "ingreso": ingreso_i, "factor": factor, "vp": vp})
    return {"total": (total if r is not None else None), "r688": r, "filas": filas, "meses": meses}


# compatibilidad: VP agregado de lo recuperado vía CMI
def vp_cmi_q_serie(conn, empresa_id, servicio):
    return ingresos_vp(conn, empresa_id, servicio)["total"]


def _year_start(fecha_inicio, i):
    """Inicio del año tarifario i de la 688 (fecha_inicio + (i-1) años)."""
    if not fecha_inicio:
        return None
    return date(fecha_inicio.year + (i - 1), fecha_inicio.month, min(fecha_inicio.day, 28))


def vp_cmi_q_activo(codigo, mods, cmi_cod, serie_q, r688, fecha_inicio):
    """VP(CMI688ⱼ×Q) de un activo: Σ CMIⱼ,ᵢ·Qᵢ/(1+r688)^i, con el CMI de la modificación vigente en el año i."""
    cc = cmi_cod.get(codigo)
    if not cc or r688 is None:
        return None
    tot = 0.0
    for i, q in serie_q.items():
        cmi = poir.cmi_aplicable(mods, cc, _year_start(fecha_inicio, i))
        if cmi is not None and q is not None:
            tot += cmi * q / ((1 + r688) ** i)
    return tot


def via_de_ejecucion(a, r688):
    """VIA688 de un activo del POIR a partir de su ejecución: ejecución/(1+r688)^año."""
    if a["via688"] is not None:
        return float(a["via688"])
    if a["ejecucion_real"] is not None and a["anio_poir"] and r688 is not None:
        return float(a["ejecucion_real"]) / ((1 + r688) ** int(a["anio_poir"]))
    return None


def bcr0_calculo(conn, empresa_id, r_emp=None):
    """BCR₀ por servicio y componente con compensación de VA₀<0 (art. 2.1.2.1.5.2.1.1).

    VA₀ por activo = va0 almacenado, o VPR₀·(1+r688)^t·fa0, o (fallback) valor_pendiente.
    Compensa negativos contra positivos del mismo servicio+componente (prioridad menor PRR).
    CI = Σcak + BCR₀·r; CMI_BCR = CI/CCP.
    """
    emp_row = conn.execute(text(
        "SELECT r, suscriptores_seg, fecha_inicio_688 FROM empresa WHERE id=:e"),
        {"e": empresa_id}).mappings().first()
    if r_emp is None:
        r_emp = float(emp_row["r"]) if (emp_row and emp_row["r"] is not None) else 0.0
    # Valores que ya no se digitan: el r688 lo da el segmento de la 688; los IPC salen de la
    # tabla; la fecha de inicio 688, de la empresa; el CCP, de los consumos del año base.
    seg688 = segmento_688(emp_row["suscriptores_seg"]) if emp_row else None
    r688_auto = r688_de_segmento(seg688)
    i14, i25 = ipc_dic(conn, 2014), ipc_dic(conn, 2025)
    fa0_auto = (float(i25) / float(i14)) if (i14 and i25) else None
    fecha_auto = emp_row["fecha_inicio_688"] if emp_row else None
    ps = params(conn, empresa_id)
    activos = lista(conn, empresa_id)
    out = {}
    for s in ("acueducto", "alcantarillado"):
        p = ps.get(s)
        r688 = float(p["r688"]) if (p and p["r688"] is not None) else r688_auto
        fecha_inicio = (p["fecha_inicio_688"] if (p and p["fecha_inicio_688"]) else fecha_auto)
        t = _t_anios(fecha_inicio) if fecha_inicio else None
        fa0 = _fa0(p) if (p and p["ipc_dic_2014"] and p["ipc_dic_2025"]) else fa0_auto
        ccp = float(p["ccp_2025"]) if (p and p["ccp_2025"] is not None) else ccp_desde_consumos(conn, empresa_id, s)
        vping = ingresos_vp(conn, empresa_id, s)["total"]          # VP de los ingresos (agregado)
        mods = poir.mods_list(conn, empresa_id, s)
        cmi_cod = poir.cmi_por_codigo(conn, empresa_id, s)         # CMI por activo por modificación
        serie_q = {}   # Q anual = Σ de los meses del año (serie mensual)
        for x in serie_list(conn, empresa_id, s):
            if x["q_m3"] is not None:
                a_i = int(x["anio_tarifario"])
                serie_q[a_i] = (serie_q.get(a_i) or 0.0) + float(x["q_m3"])
        suma_via = sum(via_de_ejecucion(a, r688) or 0.0 for a in activos
                       if a["servicio"] == s and a["vpr0"] is None and a["va0"] is None
                       and not (a["codigo"] and a["codigo"] in cmi_cod))
        comp = {1: {"pos": [], "neg": 0.0}, 2: {"pos": [], "neg": 0.0}, 3: {"pos": [], "neg": 0.0}}
        for a in activos:
            if a["servicio"] != s:
                continue
            va0 = a["va0"]
            if va0 is None and a["vpr0"] is not None and r688 is not None and t is not None and fa0 is not None:
                va0 = float(a["vpr0"]) * ((1 + r688) ** t) * fa0
            # Ingresos por proyecto: VP(CMI×Q) por activo con la modificación vigente año a año
            if (va0 is None and a["vpr0"] is None and a["codigo"] and r688 is not None
                    and t is not None and fa0 is not None):
                vpq = vp_cmi_q_activo(a["codigo"], mods, cmi_cod, serie_q, r688, fecha_inicio)
                via = via_de_ejecucion(a, r688)
                if vpq is not None and via is not None:
                    va0 = (via - vpq) * ((1 + r688) ** t) * fa0
            # Fallback: VIA688 sin VPR₀, repartiendo el VP de ingresos agregado por VIA
            if (va0 is None and a["vpr0"] is None and a["via688"] is not None and vping is not None
                    and suma_via and r688 is not None and t is not None and fa0 is not None):
                vp_j = vping * (float(a["via688"]) / suma_via)
                va0 = (float(a["via688"]) - vp_j) * ((1 + r688) ** t) * fa0
            if va0 is None:
                va0 = a["valor_pendiente"]
            if va0 is None:
                continue
            va0 = float(va0)
            prr = float(a["plazo_remanente"]) if a["plazo_remanente"] is not None else None
            ca = float(a["cuota_anual"]) if a["cuota_anual"] is not None else None
            k = a["componente"] if a["componente"] in comp else 3
            if va0 >= 0:
                comp[k]["pos"].append({"va0": va0, "prr": prr, "ca": ca})
            else:
                comp[k]["neg"] += -va0
        serv = {"bcr": 0.0, "cak": 0.0, "descuento": 0.0, "comp": {}}
        for k, g in comp.items():
            negtot = g["neg"]
            serv["descuento"] += negtot
            # compensar: absorber negativos en positivos, prioridad menor PRR
            for a in sorted(g["pos"], key=lambda x: (x["prr"] if x["prr"] is not None else 1e9), reverse=False):
                if negtot <= 0:
                    a["va0d"] = a["va0"]
                    continue
                take = min(a["va0"], negtot)
                a["va0d"] = a["va0"] - take
                negtot -= take
            bcr_k = sum(a["va0d"] for a in g["pos"])
            cak_k = 0.0
            for a in g["pos"]:
                if a["ca"] is not None:
                    cak_k += a["ca"]
                elif a["prr"] and a["prr"] > 0:
                    cak_k += a["va0d"] / a["prr"]
            serv["comp"][k] = {"bcr": bcr_k, "cak": cak_k, "n": len(g["pos"])}
            serv["bcr"] += bcr_k
            serv["cak"] += cak_k
        serv["ci"] = serv["cak"] + serv["bcr"] * r_emp
        serv["cmi_bcr"] = (serv["ci"] / ccp) if ccp else None
        serv["ccp"] = ccp
        serv["r688"] = r688
        serv["t"] = t
        serv["fa0"] = fa0
        serv["vp_ingresos"] = vping
        serv["seg688"] = seg688
        serv["sin_param"] = r688 is None          # sin r688 (segmento 688) no se puede derivar el VA₀
        out[s] = serv
    out["_r"] = r_emp
    out["_seg688"] = seg688
    out["_ipc_14"] = float(i14) if i14 else None
    out["_ipc_25"] = float(i25) if i25 else None
    out["_fecha_688"] = str(fecha_auto) if fecha_auto else None
    return out


def eliminar(conn, empresa_id, aid):
    conn.execute(text("DELETE FROM bcr_activo WHERE empresa_id=:e AND id=:i"),
                 {"e": empresa_id, "i": aid})


def resumen(conn, empresa_id):
    """BCR₀ por servicio y componente (suma de valor pendiente por recuperar) y cuota anual."""
    rows = conn.execute(text(
        "SELECT servicio, componente, count(*) AS n, "
        "       coalesce(sum(valor_pendiente),0) AS bcr, coalesce(sum(cuota_anual),0) AS cuota "
        "FROM bcr_activo WHERE empresa_id=:e GROUP BY servicio, componente"),
        {"e": empresa_id}).mappings().all()
    por_serv = {}
    for r in rows:
        s = por_serv.setdefault(r["servicio"], {"bcr": 0.0, "cuota": 0.0, "n": 0, "comp": {}})
        s["bcr"] += float(r["bcr"] or 0); s["cuota"] += float(r["cuota"] or 0); s["n"] += r["n"]
        s["comp"][r["componente"]] = {"bcr": float(r["bcr"] or 0), "cuota": float(r["cuota"] or 0), "n": r["n"]}
    return por_serv


# ---------------- Plan / ejecución / cumplimiento por año tarifario ----------------
def plan_por_anio(conn, empresa_id, servicio=None):
    sql = ("SELECT EXTRACT(YEAR FROM fecha_planeada_operacion)::int AS anio, "
           "       coalesce(sum(valor_planeado),0) AS planeado, count(*) AS n "
           "FROM proyecto_inversion WHERE empresa_id=:e AND fecha_planeada_operacion IS NOT NULL")
    p = {"e": empresa_id}
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " GROUP BY 1 ORDER BY 1"
    return {int(r[0]): {"planeado": float(r[1] or 0), "n": r[2]}
            for r in conn.execute(text(sql), p).all() if r[0]}


def real_por_anio(conn, empresa_id, servicio=None):
    """Ejecutado acumulado por año = suma del último corte (mes mayor) de cada proyecto en el año."""
    sql = ("SELECT a.anio, coalesce(sum(a.avance_financiero),0) AS ejecutado "
           "FROM (SELECT DISTINCT ON (ai.proyecto_id, ai.anio) ai.proyecto_id, ai.anio, "
           "             ai.avance_financiero "
           "      FROM avance_inversion ai JOIN proyecto_inversion p ON p.id=ai.proyecto_id "
           "      WHERE ai.empresa_id=:e" + (" AND p.servicio=:s" if servicio else "") +
           "      ORDER BY ai.proyecto_id, ai.anio, ai.mes DESC) a GROUP BY a.anio ORDER BY a.anio")
    p = {"e": empresa_id}
    if servicio:
        p["s"] = servicio
    return {int(r[0]): float(r[1] or 0) for r in conn.execute(text(sql), p).all()}


def cumplimiento(conn, empresa_id, servicio=None, umbral=0.80):
    plan = plan_por_anio(conn, empresa_id, servicio)
    real = real_por_anio(conn, empresa_id, servicio)
    anios = sorted(set(plan) | set(real))
    out = []
    for a in anios:
        pl = plan.get(a, {}).get("planeado", 0.0)
        ej = real.get(a, 0.0)
        pct = (ej / pl * 100.0) if pl else None
        out.append({"anio": a, "planeado": pl, "ejecutado": ej, "pct": pct,
                    "supera": (pct is not None and pct >= umbral * 100.0),
                    "en_curso": ej > 0 and (pct is None or pct < umbral * 100.0)})
    return out


# ---------------- Demanda y proyección del CMI ----------------
def demanda_anual(conn, empresa_id, servicio):
    """m³ anuales a partir de lo facturado (anualiza si hay menos de 12 meses). None si no hay datos."""
    row = conn.execute(text(
        "SELECT coalesce(sum(m3_facturados),0) AS m3, count(*) AS n "
        "FROM carga_mensual WHERE empresa_id=:e AND servicio=:s AND cod_dane='' AND m3_facturados IS NOT NULL"),
        {"e": empresa_id, "s": servicio}).mappings().first()
    if not row or not row["n"] or not row["m3"]:
        return None
    m3 = float(row["m3"]); n = int(row["n"])
    return m3 * (12.0 / n) if n < 12 else m3


def proyeccion(conn, empresa_id, servicio, r, demanda=None, horizonte=5, anio0=2027, vida_util=20.0):
    """Proyección indicativa del CMI ($/m³) para `horizonte` años desde `anio0`.

    Supuestos: la BCR₀ se remunera a la tasa r y recupera su cuota anual; los
    proyectos del POIR entran a la BCR en su año planeado (se asume ejecución ≥80 %)
    y aportan CMI_POIR como anualidad (remuneración + depreciación lineal a `vida_util`).
    """
    calc = bcr0_calculo(conn, empresa_id, r).get(servicio, {"bcr": 0.0, "cak": 0.0})
    bcr = float(calc.get("bcr") or 0.0); cuota = float(calc.get("cak") or 0.0)
    if demanda is None:
        demanda = demanda_anual(conn, empresa_id, servicio)
    if demanda is None:
        p = param_get(conn, empresa_id, servicio)   # fallback: CCP 2025 cargado en los parámetros 688
        if p and p["ccp_2025"]:
            demanda = float(p["ccp_2025"])
    plan = plan_por_anio(conn, empresa_id, servicio)
    poir_acum = 0.0
    filas = []
    for k in range(horizonte):
        a = anio0 + k
        entra = plan.get(a, {}).get("planeado", 0.0)       # POIR que entra en operación ese año
        bcr = max(bcr - cuota, 0.0) + entra                 # roll-forward indicativo de la BCR
        poir_acum += entra
        rem_bcr = bcr * r
        rem_poir = poir_acum * r + (poir_acum / vida_util if vida_util else 0.0)
        cmi_bcr = (rem_bcr + cuota) / demanda if demanda else None
        cmi_poir = rem_poir / demanda if demanda else None
        cmi_tot = (cmi_bcr + cmi_poir) if (cmi_bcr is not None and cmi_poir is not None) else None
        filas.append({"anio": a, "bcr": bcr, "poir_entra": entra, "poir_acum": poir_acum,
                      "cmi_bcr": cmi_bcr, "cmi_poir": cmi_poir, "cmi_total": cmi_tot})
    return {"servicio": servicio, "bcr0": bcr, "cuota": cuota, "r": r,
            "demanda": demanda, "vida_util": vida_util, "filas": filas}
