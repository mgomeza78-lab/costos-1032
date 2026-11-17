# -*- coding: utf-8 -*-
"""Comparación tarifaria — costos unitarios 1032 (nuevos) vs. última tarifa vigente (688/825).

Submenú de «Costo de referencia». Compara, a precios del MISMO mes, los cargos que arroja el
sistema bajo la Res. CRA 1032 (CF = CMA; CC = CMO + CMI + CMICT, art. 2.1.2.1.3) contra la última
tarifa que la empresa venía aplicando bajo la metodología anterior (Res. CRA 688/2014, insumo del
período de inicio, art. 2.1.2.1.1.8, tabla `costo_referencia_688`).

Para que la variación no mezcle efecto de precios con efecto de metodología, AMBAS series se llevan
al mismo mes de referencia M:
  · la 1032 se indexa desde su base (dic de i-1) con las dos canastas de la 1032 (IPCs para
    CMA/CMO/CMICT; IPC para CMI, art. 2.1.2.1.5.3.1);
  · la 688 vigente se indexa desde su `fecha_indexacion` con el IPC total (indexación del marco 688).
El mes M se elige con el modo: «última actualización» (mes de la última aprobación 688) o «próximo
recálculo» (último mes de índice disponible, con el que se aplica la 1032).

La factura se arma como tarifa plena (sin subsidios/contribuciones) = CF + CC·Q, por servicio y como
factura conjunta (acueducto + alcantarillado sobre el mismo consumo medido Q). El impacto se evalúa a
distintos niveles de consumo y, de forma destacada, al ICUF (Índice de Consumo Unitario Facturado =
AF/N, art. del CCP 2.1.2.1.3.3) — calculado por CLASE DE USO (estratos 1–6 y no residenciales) para
que los grandes consumidores no distorsionen el promedio, más el ICUF global como referencia.

No inventa datos: lo que falte (índices, componentes, 688 vigente, comercial por clase) se marca.
"""
from sqlalchemy import text
import periodos as per
import ref688_service as ref688
import ccp_view as cv

SERV_NOMBRE = {"acueducto": "Acueducto", "alcantarillado": "Alcantarillado"}
VISTAS = [("conjunta", "Factura conjunta"), ("acueducto", "Acueducto"), ("alcantarillado", "Alcantarillado")]

# Componentes semejantes 1032 ↔ 688. El CMICT de la 1032 (impuestos, contribuciones y tasas) es el
# equivalente del CMT (Costo Medio de Tasas) del marco 688. Campo del desglose en costo_referencia_688.
#   (clave_1032, equiv_688, descripción, unidad, canasta_1032, campo_688)
COMPS = [
    ("CMA", "CMA", "Costo Medio de Administración", "$/susc·mes", "ipcs", "cma"),
    ("CMO", "CMO", "Costo Medio de Operación", "$/m³", "ipcs", "cmo"),
    ("CMI", "CMI", "Costo Medio de Inversión", "$/m³", "ipc", "cmi"),
    ("CMICT", "CMT", "Impuestos, contribuciones y tasas", "$/m³", "ipcs", "cmict"),
]

# Clases de uso del SUI (CLASEUSO) — residenciales 1–6 y no residenciales.
CLASES = [(1, "Estrato 1", "res"), (2, "Estrato 2", "res"), (3, "Estrato 3", "res"),
          (4, "Estrato 4", "res"), (5, "Estrato 5", "res"), (6, "Estrato 6", "res"),
          (11, "Comercial", "nor"), (10, "Industrial", "nor"),
          (12, "Oficial", "nor"), (13, "Especial", "nor")]
CLASE_NOMBRE = {c: n for c, n, _ in CLASES}

MESES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
         7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}
BASICO_DEFECTO = 16.0          # consumo básico a < 1000 msnm (Res. CRA 750/2016); marca de referencia
QMAX = 40.0                    # tope de la curva de factura (m³/mes)
NIVELES_TABLA = [0, 6, 11, 16, 20, 30, 40]   # niveles de consumo de la tabla de factura


# ───────────────────────── índices e insumos ─────────────────────────
def _idx(conn):
    """{(anio, mes): (ipc, ipcs)} con ipcs→ipc si no está cargado (indice_ipc)."""
    out = {}
    for r in conn.execute(text(
            "SELECT anio, mes, indice, ipcs FROM indice_ipc WHERE indice IS NOT NULL")).mappings().all():
        ipc = float(r["indice"])
        ipcs = float(r["ipcs"]) if r["ipcs"] is not None else ipc
        out[(int(r["anio"]), int(r["mes"]))] = (ipc, ipcs)
    return out


def _fac(idx, col, de, a):
    """Razón de índice de `de` a `a` (col 0 = IPC, col 1 = IPCs). None si falta algún mes."""
    vd, va = idx.get(de), idx.get(a)
    if not vd or not va or not vd[col]:
        return None
    return va[col] / vd[col]


def _mes_de(fecha):
    """(anio, mes) de un date/str 'YYYY-MM[-DD]'; None si no se puede."""
    if fecha is None:
        return None
    if hasattr(fecha, "year"):
        return (int(fecha.year), int(fecha.month))
    partes = str(fecha).strip().split("-")
    try:
        return (int(partes[0]), int(partes[1]))
    except (ValueError, IndexError):
        return None


def _mes_lbl(m):
    return f"{MESES.get(m[1], m[1])}-{m[0]}" if m else "—"


def _componentes_1032(conn, eid):
    """{servicio: {CMA, CMO, CMI, CMICT}} del resultado del sistema (resultado_componente)."""
    out = {}
    for r in conn.execute(text(
            "SELECT servicio, componente, valor FROM resultado_componente "
            "WHERE empresa_id=:e AND componente IN ('CMA','CMO','CMI','CMICT')"),
            {"e": eid}).mappings().all():
        out.setdefault(r["servicio"], {})[r["componente"]] = (
            float(r["valor"]) if r["valor"] is not None else None)
    return out


# ───────────────────────── cargos 1032 y 688 a mes M ─────────────────────────
def _cargos_1032(c, idx, base, M):
    """(cf, cc, falta[]) de la 1032 a precios de M. CF = CMA; CC = CMO+CMI+CMICT (canastas 1032)."""
    fs = _fac(idx, 1, base, M)      # IPCs → CMA/CMO/CMICT
    fi = _fac(idx, 0, base, M)      # IPC  → CMI
    falta = []
    cma, cmo, cmi, cmict = c.get("CMA"), c.get("CMO"), c.get("CMI"), c.get("CMICT")
    cf = cma * fs if (cma is not None and fs is not None) else None
    if cma is None:
        falta.append("CMA (1032)")
    if fs is None:
        falta.append(f"IPCs {_mes_lbl(base)}/{_mes_lbl(M)}")
    # CC: suma de las partes disponibles; marca las que falten.
    cc_partes, hay = 0.0, False
    for k, val, fa in (("CMO", cmo, fs), ("CMI", cmi, fi), ("CMICT", cmict, fs)):
        if val is None:
            falta.append(f"{k} (1032)")
        elif fa is None:
            pass   # el factor ya quedó marcado arriba (fs) o se marca para IPC-CMI abajo
        else:
            cc_partes += val * fa
            hay = True
    if cmi is not None and fi is None:
        falta.append(f"IPC {_mes_lbl(base)}/{_mes_lbl(M)}")
    cc = cc_partes if hay else None
    return cf, cc, falta


def _cargos_688(r, idx, M):
    """(cf, cc, fecha, falta[]) de la 688 vigente a precios de M (IPC total desde su fecha)."""
    falta = []
    if not r:
        return None, None, None, ["tarifa 688 vigente (cargar en «Punto de partida 688»)"]
    fecha = _mes_de(r.get("fecha_indexacion"))
    if not fecha:
        return (r.get("cargo_fijo"), r.get("cargo_consumo"), None,
                ["fecha de indexación de la 688"])
    f = _fac(idx, 0, fecha, M)     # IPC total (indexación del marco 688)
    if f is None:
        falta.append(f"IPC {_mes_lbl(fecha)}/{_mes_lbl(M)}")
    cfv, ccv = r.get("cargo_fijo"), r.get("cargo_consumo")
    cf = float(cfv) * f if (cfv is not None and f is not None) else None
    cc = float(ccv) * f if (ccv is not None and f is not None) else None
    if cfv is None:
        falta.append("cargo fijo 688")
    if ccv is None:
        falta.append("cargo por consumo 688")
    return cf, cc, fecha, falta


def _comp_1032_M(c, idx, base, M):
    """Componentes 1032 (CMA/CMO/CMI/CMICT) a precios de M, cada uno con su canasta."""
    fs, fi = _fac(idx, 1, base, M), _fac(idx, 0, base, M)   # IPCs / IPC
    out = {}
    for clave, _e, _d, _u, canasta, _campo in COMPS:
        v = c.get(clave)
        fa = fi if canasta == "ipc" else fs
        out[clave] = (v * fa) if (v is not None and fa is not None) else None
    return out


def _comp_688_M(r, idx, M):
    """Componentes del desglose 688 (cma/cmo/cmi/cmict≡CMT) a precios de M, con IPC total."""
    out = {k: None for k, *_ in COMPS}
    if not r:
        return out
    fecha = _mes_de(r.get("fecha_indexacion"))
    f = _fac(idx, 0, fecha, M) if fecha else None
    for clave, _e, _d, _u, _canasta, campo in COMPS:
        v = r.get(campo)
        out[clave] = (float(v) * f) if (v is not None and f is not None) else None
    return out


def _var(nuevo, viejo):
    """(Δabs, Δ%) de nuevo vs. viejo; (None, None) si falta alguno."""
    if nuevo is None or viejo is None:
        return None, None
    d = nuevo - viejo
    return d, (d / viejo * 100.0 if viejo else None)


def _factura(cf, cc, q):
    if cf is None or cc is None:
        return None
    return cf + cc * q


def _factores(conn, eid, vigencia):
    """{(servicio, clase): (factor_cargofijo, factor_consumo)} del acuerdo del concejo para la
    vigencia; si no hay para esa vigencia, usa la última vigencia cargada. (dict, hay, vigencia_usada)."""
    def _carga(v):
        return conn.execute(text(
            "SELECT servicio, clase, factor_cargofijo, factor_consumo FROM factor_subsidio "
            "WHERE empresa_id=:e AND vigencia=:v"), {"e": eid, "v": int(v)}).mappings().all()
    rows = _carga(vigencia)
    v_usada = int(vigencia)
    if not rows:
        v2 = conn.execute(text("SELECT max(vigencia) FROM factor_subsidio WHERE empresa_id=:e"),
                          {"e": eid}).scalar()
        if v2:
            rows, v_usada = _carga(v2), int(v2)
    out = {}
    for r in rows:
        out[(r["servicio"], int(r["clase"]))] = (float(r["factor_cargofijo"] or 0.0),
                                                 float(r["factor_consumo"] or 0.0))
    return out, bool(rows), v_usada


def _factura_neta(cf, cc, q, fcf, fcc, basico):
    """Factura por suscriptor con subsidio/contribución. Subsidio (fcc<0): factor sobre el cargo fijo
    y el consumo básico; el excedente, a tarifa plena. Contribución (fcc≥0): factor sobre el cargo fijo
    y el consumo total (Ley 142/1994, arts. 89, 99 y 100)."""
    if cf is None or cc is None:
        return None
    cf_n = cf * (1.0 + (fcf or 0.0))
    if (fcc or 0.0) >= 0.0:                       # contribución (o neutro) → consumo total
        cc_n = cc * q * (1.0 + (fcc or 0.0))
    else:                                         # subsidio → solo el consumo básico
        qb = min(q, basico)
        cc_n = cc * (qb * (1.0 + fcc) + max(q - qb, 0.0))
    return cf_n + cc_n


# ───────────────────────── ICUF por clase de uso ─────────────────────────
def _icuf_por_clase(conn, eid, anio):
    """ICUF (= AF/N) por clase de uso, del acueducto (consumo medido que factura ambos servicios),
    sobre el año base `anio`. {clase: {n, af, icuf}} + total global."""
    out, tot_n, tot_af = {}, 0.0, 0.0
    for r in conn.execute(text(
            "SELECT clase, COALESCE(SUM(suscriptores),0) n, COALESCE(SUM(m3),0) af "
            "FROM carga_mensual_detalle WHERE empresa_id=:e AND anio=:a AND servicio='acueducto' "
            "GROUP BY clase"), {"e": eid, "a": int(anio)}).mappings().all():
        n, af = float(r["n"] or 0), float(r["af"] or 0)
        out[int(r["clase"])] = {"n": n, "af": af, "icuf": (af / n if n else None)}
        tot_n += n
        tot_af += af
    glob = (tot_af / tot_n) if tot_n else None
    return out, glob


# ───────────────────────── gráfica de factura vs consumo ─────────────────────────
def _curva(cf688, cc688, cf1032, cc1032, qmax, basico, icuf_q):
    """Geometría SVG de dos rectas de factura (688 y 1032) sobre Q∈[0, qmax], con marcas."""
    if None in (cf688, cc688, cf1032, cc1032):
        return None
    W, H, ML, MR, MT, MB = 660.0, 280.0, 68.0, 18.0, 16.0, 40.0
    pw, ph = W - ML - MR, H - MT - MB
    f688_max, f1032_max = cf688 + cc688 * qmax, cf1032 + cc1032 * qmax
    vmax = max(cf688, cf1032, f688_max, f1032_max, 1.0)

    def X(q):
        return round(ML + (q / qmax) * pw, 1)

    def Y(v):
        return round(MT + (1 - v / vmax) * ph, 1)

    marcas = []
    for q, lab, cls in ((basico, f"básico {int(basico)}", "basico"),
                        (icuf_q, f"ICUF {icuf_q:.1f}".replace(".", ","), "icuf")):
        if q is not None and 0 <= q <= qmax:
            marcas.append({"x": X(q), "lbl": lab, "cls": cls,
                           "y688": Y(cf688 + cc688 * q), "y1032": Y(cf1032 + cc1032 * q),
                           "f688": cf688 + cc688 * q, "f1032": cf1032 + cc1032 * q})
    # Marcas del eje Y (0, mitad, vmax).
    yticks = [{"v": v, "y": Y(v), "lbl": _mil(v)} for v in (0.0, vmax / 2, vmax)]
    xticks = [{"q": q, "x": X(q), "lbl": str(int(q))} for q in (0, 10, 20, 30, int(qmax))]
    return {"W": W, "H": H, "x0": ML, "x1": ML + pw, "y0": MT, "y1": MT + ph,
            "l688": {"x1": X(0), "y1": Y(cf688), "x2": X(qmax), "y2": Y(f688_max)},
            "l1032": {"x1": X(0), "y1": Y(cf1032), "x2": X(qmax), "y2": Y(f1032_max)},
            "marcas": marcas, "yticks": yticks, "xticks": xticks, "vmax": vmax}


def _mil(v):
    try:
        return f"${int(round(v)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


# ───────────────────────── paquete para la vista ─────────────────────────
def resumen(conn, eid, modo="proximo", vista="conjunta", mes_param=None, base="neta"):
    """Arma toda la comparación. `modo`: 'ultima' | 'proximo'. `vista`: 'conjunta'|'acueducto'|
    'alcantarillado'. `mes_param`: 'YYYY-MM' que fuerza el mes de referencia (gana sobre el modo).
    `base`: 'neta' (aplica subsidios/contribuciones) | 'plena' (tarifa sin factores)."""
    base = base if base in ("plena", "neta") else "neta"
    sel = per.POR_CLAVE["inicio"]
    dic_ref = sel["anio"] - 1                 # 2025 (i-1)
    base_1032 = (dic_ref, 12)                 # dic-2025 — base de los costos 1032
    anio_icuf = sel["anios_base"][-1]         # 2025 — consumo representativo (i-1)

    idx = _idx(conn)
    comp = _componentes_1032(conn, eid)
    ref = ref688.por_servicio(conn, eid)
    servicios = [s for s in ("acueducto", "alcantarillado") if s in comp or s in ref]

    # Mes de referencia M.
    meses_688 = [m for m in (_mes_de((ref.get(s) or {}).get("fecha_indexacion")) for s in servicios) if m]
    m_ultima = max(meses_688) if meses_688 else None
    m_proximo = max(idx) if idx else None
    M = None
    if mes_param:
        try:
            a, mm = mes_param.split("-")[:2]
            M = (int(a), int(mm))
        except (ValueError, IndexError):
            M = None
    if M is None:
        M = m_ultima if modo == "ultima" else m_proximo
        modo = "ultima" if modo == "ultima" else "proximo"

    # Cargos por servicio (CF/CC) 688 y 1032 a precios de M, con sus variaciones.
    serv = {}
    falta_global = []
    comp1032_bs, comp688_bs = {}, {}
    for s in servicios:
        comp1032_bs[s] = _comp_1032_M(comp.get(s, {}), idx, base_1032, M)
        comp688_bs[s] = _comp_688_M(ref.get(s), idx, M)
        cf1032, cc1032, fa1 = _cargos_1032(comp.get(s, {}), idx, base_1032, M)
        cf688, cc688, fecha688, fa6 = _cargos_688(ref.get(s), idx, M)
        dcf = _var(cf1032, cf688)
        dcc = _var(cc1032, cc688)
        serv[s] = {"servicio": s, "nombre": SERV_NOMBRE[s],
                   "cf688": cf688, "cc688": cc688, "cf1032": cf1032, "cc1032": cc1032,
                   "dcf_abs": dcf[0], "dcf_pct": dcf[1], "dcc_abs": dcc[0], "dcc_pct": dcc[1],
                   "fecha688": fecha688, "falta": fa1 + fa6}
        falta_global += fa1 + fa6

    # Factura conjunta (suma de servicios presentes).
    def _suma(campo):
        vals = [serv[s][campo] for s in servicios if serv[s][campo] is not None]
        return sum(vals) if len(vals) == len(servicios) and servicios else None
    conj = {"cf688": _suma("cf688"), "cc688": _suma("cc688"),
            "cf1032": _suma("cf1032"), "cc1032": _suma("cc1032")}
    conj["dcf_abs"], conj["dcf_pct"] = _var(conj["cf1032"], conj["cf688"])
    conj["dcc_abs"], conj["dcc_pct"] = _var(conj["cc1032"], conj["cc688"])
    vistas_disp = [(k, n) for k, n in VISTAS if (k == "conjunta" and len(servicios) > 1) or k in servicios]
    if vista not in [k for k, _ in vistas_disp]:
        vista = vistas_disp[0][0] if vistas_disp else "acueducto"

    # CF/CC de la vista seleccionada.
    if vista == "conjunta":
        cf688, cc688, cf1032, cc1032 = conj["cf688"], conj["cc688"], conj["cf1032"], conj["cc1032"]
    else:
        cf688, cc688 = serv[vista]["cf688"], serv[vista]["cc688"]
        cf1032, cc1032 = serv[vista]["cf1032"], serv[vista]["cc1032"]

    # Variación por componente (CMA/CMO/CMI/CMICT≡CMT) de la vista seleccionada.
    def _comp_vista(bs, k):
        if vista == "conjunta":
            vals = [bs[s].get(k) for s in servicios if bs[s].get(k) is not None]
            return sum(vals) if (len(vals) == len(servicios) and servicios) else None
        return bs.get(vista, {}).get(k)
    componentes = []
    for clave, equiv, desc, unidad, _canasta, _campo in COMPS:
        v688 = _comp_vista(comp688_bs, clave)
        v1032 = _comp_vista(comp1032_bs, clave)
        dabs, dpct = _var(v1032, v688)
        componentes.append({"clave": clave, "equiv": equiv, "desc": desc, "unidad": unidad,
                            "v688": v688, "v1032": v1032, "dabs": dabs, "dpct": dpct})
    hay_688_comp = any(r["v688"] is not None for r in componentes)

    # Factores de subsidio/contribución (Acuerdo del concejo, por servicio y clase; art. 89 Ley 142).
    factores, hay_factores, vig_fac = _factores(conn, eid, sel["anio"])
    usar_neta = (base == "neta") and hay_factores
    basico = BASICO_DEFECTO

    # ICUF por clase de uso (acueducto, año i-1) + global.
    icuf_clase, icuf_glob = _icuf_por_clase(conn, eid, anio_icuf)

    def _bill(marco, q, clase):
        """Factura de la vista (plena o neta según `base`) para un consumo q y una clase."""
        if q is None:
            return None
        cfv = cf688 if marco == "688" else cf1032
        ccv = cc688 if marco == "688" else cc1032
        if not usar_neta:
            return _factura(cfv, ccv, q)
        if vista == "conjunta":
            tot = 0.0
            for s in servicios:
                fcf, fcc = factores.get((s, clase), (0.0, 0.0))
                v = _factura_neta(serv[s]["cf" + marco], serv[s]["cc" + marco], q, fcf, fcc, basico)
                if v is None:
                    return None
                tot += v
            return tot
        fcf, fcc = factores.get((vista, clase), (0.0, 0.0))
        return _factura_neta(cfv, ccv, q, fcf, fcc, basico)

    serv_fac = "acueducto" if vista == "conjunta" else vista
    por_clase = []
    for cod, nombre, grupo in CLASES:
        d = icuf_clase.get(cod)
        q = d["icuf"] if d else None
        fcf_r, fcc_r = factores.get((serv_fac, cod), (0.0, 0.0))
        f688, f1032 = _bill("688", q, cod), _bill("1032", q, cod)
        dabs, dpct = _var(f1032, f688)
        por_clase.append({"clase": cod, "nombre": nombre, "grupo": grupo,
                          "n": (d["n"] if d else None), "icuf": q, "fcf": fcf_r, "fcc": fcc_r,
                          "f688": f688, "f1032": f1032, "dabs": dabs, "dpct": dpct})
    hay_clases = any(x["icuf"] is not None for x in por_clase)

    # Titular: plena → factura al ICUF global; neta → factura MEDIA PONDERADA por suscriptores
    # (con subsidios/contribuciones) sobre la mezcla real de clientes.
    if usar_neta:
        num6 = num10 = den = 0.0
        for row in por_clase:
            if row["icuf"] is not None and row["n"] and row["f688"] is not None and row["f1032"] is not None:
                num6 += row["n"] * row["f688"]
                num10 += row["n"] * row["f1032"]
                den += row["n"]
        avg6 = num6 / den if den else None
        avg10 = num10 / den if den else None
        titular = {"neta": True, "icuf": icuf_glob, "f688": avg6, "f1032": avg10}
        titular["dabs"], titular["dpct"] = _var(avg10, avg6)
    else:
        f688_g = _factura(cf688, cc688, icuf_glob) if icuf_glob is not None else None
        f1032_g = _factura(cf1032, cc1032, icuf_glob) if icuf_glob is not None else None
        titular = {"neta": False, "icuf": icuf_glob, "f688": f688_g, "f1032": f1032_g}
        titular["dabs"], titular["dpct"] = _var(f1032_g, f688_g)

    # Tabla de factura por nivel de consumo (vista seleccionada) + fila del ICUF global.
    niveles = sorted(set(NIVELES_TABLA + ([round(icuf_glob, 1)] if icuf_glob else [])))
    tabla = []
    for q in niveles:
        f688 = _factura(cf688, cc688, q)
        f1032 = _factura(cf1032, cc1032, q)
        dabs, dpct = _var(f1032, f688)
        tabla.append({"q": q, "es_icuf": icuf_glob is not None and abs(q - round(icuf_glob, 1)) < 1e-6,
                      "es_basico": abs(q - BASICO_DEFECTO) < 1e-6,
                      "f688": f688, "f1032": f1032, "dabs": dabs, "dpct": dpct})

    chart = _curva(cf688, cc688, cf1032, cc1032, QMAX, BASICO_DEFECTO, icuf_glob)

    # Selector de mes (meses de índice disponibles, desc).
    meses_sel = [{"val": f"{a}-{m:02d}", "lbl": _mes_lbl((a, m)), "sel": (a, m) == M}
                 for (a, m) in sorted(idx, reverse=True)]

    return {
        "vistas": vistas_disp, "vista": vista,
        "modo": modo, "M": M, "M_lbl": _mes_lbl(M),
        "m_ultima_lbl": _mes_lbl(m_ultima), "m_proximo_lbl": _mes_lbl(m_proximo),
        "base_1032_lbl": _mes_lbl(base_1032), "anio_icuf": anio_icuf,
        "meses_sel": meses_sel,
        "serv": [serv[s] for s in servicios], "conj": conj if len(servicios) > 1 else None,
        "cf688": cf688, "cc688": cc688, "cf1032": cf1032, "cc1032": cc1032,
        "componentes": componentes, "hay_688_comp": hay_688_comp,
        "titular": titular, "por_clase": por_clase, "hay_clases": hay_clases,
        "base": base, "usar_neta": usar_neta, "hay_factores": hay_factores, "vig_fac": vig_fac,
        "tabla": tabla, "chart": chart, "qmax": QMAX, "basico": BASICO_DEFECTO,
        "hay_688": any(ref.get(s) for s in servicios),
        "hay_1032": any(comp.get(s) for s in servicios),
        "falta": sorted(set(falta_global)),
    }
