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
              "fo": (d.get("fecha_operacion") or None), "u": usuario_id}
    aid = d.get("id")
    if aid:
        conn.execute(text(
            "UPDATE bcr_activo SET servicio=:s, componente=:c, nombre=:n, cod_dane=:cd, "
            " valor_bruto=:vb, plazo_remanente=:pr, cuota_anual=:ca, valor_pendiente=:vp, "
            " origen=:og, observacion=:ob, tipo_activo=:ta, vida_util=:vu, via688=:via, "
            " vp_cmi_q=:vpcq, vpr0=:vpr, va0=:va0, anio_poir=:ap, ejecucion_real=:er, "
            " fecha_operacion=:fo, actualizado_en=now() WHERE empresa_id=:e AND id=:i"),
            {**campos, "i": aid})
        return aid, None
    aid = conn.execute(text(
        "INSERT INTO bcr_activo(empresa_id,servicio,componente,nombre,cod_dane,valor_bruto,"
        " plazo_remanente,cuota_anual,valor_pendiente,origen,observacion,tipo_activo,vida_util,"
        " via688,vp_cmi_q,vpr0,va0,anio_poir,ejecucion_real,fecha_operacion,cargado_por) "
        "VALUES (:e,:s,:c,:n,:cd,:vb,:pr,:ca,:vp,:og,:ob,:ta,:vu,:via,:vpcq,:vpr,:va0,:ap,:er,:fo,:u) "
        "RETURNING id"), campos).scalar()
    return aid, None


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
        "ON CONFLICT (empresa_id,servicio) DO UPDATE SET r688=excluded.r688, "
        " ipc_dic_2014=excluded.ipc_dic_2014, ipc_dic_2025=excluded.ipc_dic_2025, "
        " fecha_inicio_688=excluded.fecha_inicio_688, provision_poir=excluded.provision_poir, "
        " ccp_2025=excluded.ccp_2025, observacion=excluded.observacion, actualizado_en=now()"),
        {"e": empresa_id, "s": servicio, "r": d.get("r688"), "i14": d.get("ipc_dic_2014"),
         "i25": d.get("ipc_dic_2025"), "f": d.get("fecha_inicio_688") or None,
         "pv": d.get("provision_poir"), "ccp": d.get("ccp_2025"),
         "ob": (d.get("observacion") or "").strip() or None})
    return True, None


def serie_list(conn, empresa_id, servicio=None):
    sql = ("SELECT servicio, anio_tarifario, q_m3, cmi_cobrado FROM bcr_serie WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " ORDER BY servicio, anio_tarifario"
    return conn.execute(text(sql), p).mappings().all()


def serie_set(conn, empresa_id, servicio, anio_tarifario, q_m3, cmi_cobrado):
    if servicio not in SERVICIOS:
        return False, "servicio inválido"
    conn.execute(text(
        "INSERT INTO bcr_serie(empresa_id,servicio,anio_tarifario,q_m3,cmi_cobrado) "
        "VALUES (:e,:s,:a,:q,:c) ON CONFLICT (empresa_id,servicio,anio_tarifario) DO UPDATE SET "
        " q_m3=excluded.q_m3, cmi_cobrado=excluded.cmi_cobrado"),
        {"e": empresa_id, "s": servicio, "a": anio_tarifario, "q": q_m3, "c": cmi_cobrado})
    return True, None


def serie_del(conn, empresa_id, servicio, anio_tarifario):
    conn.execute(text("DELETE FROM bcr_serie WHERE empresa_id=:e AND servicio=:s AND anio_tarifario=:a"),
                 {"e": empresa_id, "s": servicio, "a": anio_tarifario})


def ingresos_vp(conn, empresa_id, servicio):
    """VP de los ingresos recuperados vía CMI = Σ CMI688ᵢ·Qᵢ/(1+r688)^i.

    Es el término VP(CMI688×Q) del VPR₀ (art. 2.1.2.1.3.5.5). Devuelve el detalle
    año a año (ingreso = CMI·Q, factor de descuento, VP del año) y el total, a
    partir de las series de agua facturada y CMI cobrado de la 688.
    """
    p = param_get(conn, empresa_id, servicio)
    r = float(p["r688"]) if p and p["r688"] is not None else None
    filas, total = [], 0.0
    for s in serie_list(conn, empresa_id, servicio):
        i = int(s["anio_tarifario"])
        q = float(s["q_m3"]) if s["q_m3"] is not None else None
        cmi = float(s["cmi_cobrado"]) if s["cmi_cobrado"] is not None else None
        ingreso = (cmi * q) if (q is not None and cmi is not None) else None
        factor = (1.0 / ((1 + r) ** i)) if r is not None else None
        vp = (ingreso * factor) if (ingreso is not None and factor is not None) else None
        if vp is not None:
            total += vp
        filas.append({"anio": i, "q": q, "cmi": cmi, "ingreso": ingreso, "factor": factor, "vp": vp})
    return {"total": (total if r is not None else None), "r688": r, "filas": filas}


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
    if r_emp is None:
        r_emp = conn.execute(text("SELECT r FROM empresa WHERE id=:e"), {"e": empresa_id}).scalar()
        r_emp = float(r_emp) if r_emp is not None else 0.0
    ps = params(conn, empresa_id)
    activos = lista(conn, empresa_id)
    out = {}
    for s in ("acueducto", "alcantarillado"):
        p = ps.get(s)
        r688 = float(p["r688"]) if p and p["r688"] is not None else None
        t = _t_anios(p["fecha_inicio_688"]) if (p and p["fecha_inicio_688"]) else None
        fa0 = _fa0(p) if p else None
        ccp = float(p["ccp_2025"]) if (p and p["ccp_2025"] is not None) else None
        vping = ingresos_vp(conn, empresa_id, s)["total"]          # VP de los ingresos (agregado)
        fecha_inicio = p["fecha_inicio_688"] if p else None
        mods = poir.mods_list(conn, empresa_id, s)
        cmi_cod = poir.cmi_por_codigo(conn, empresa_id, s)         # CMI por activo por modificación
        serie_q = {int(x["anio_tarifario"]): (float(x["q_m3"]) if x["q_m3"] is not None else None)
                   for x in serie_list(conn, empresa_id, s)}
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
        serv["sin_param"] = p is None
        out[s] = serv
    out["_r"] = r_emp
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
        "FROM carga_mensual WHERE empresa_id=:e AND servicio=:s AND m3_facturados IS NOT NULL"),
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
