# -*- coding: utf-8 -*-
"""Costos operativos particulares de ENERGÍA (CE) e INSUMOS QUÍMICOS (CIQ) — Res. CRA 1032.

ENERGÍA (art. 2.1.2.1.3.4.6):
    Ceb = Σⱼ Kebⱼ × Pceⱼ      (costo de energía reconocido, por servicio)
    Kebⱼ = mín[ (FEⱼ × Vⱼ × Hⱼ) , Krⱼ ]          (consumo eficiente, kWh)
    FEⱼ  = Υ / (3600 × η)                          (factor de energía, kWh/(m³·m))
      Υ  = 9,8 kN/m³ (acueducto) · 10,5 kN/m³ (alcantarillado y combinadas)   — topes del art.
      η  = 0,60 (alcantarillado) ; en acueducto por el VOLUMEN bombeado del punto:
             V ≤ 1.000.000 m³/año → 0,63 ; 1.000.000 < V ≤ 3.000.000 → 0,69 ; V > 3.000.000 → 0,77
           (parágrafo: η mínimo por punto; el 2.º segmento no puede usar la excepción de η < 60 %).
    Castigo por eficiencia (informativo) = Krⱼ×Pceⱼ − Kebⱼ×Pceⱼ  (lo que se deja de reconocer por sobreconsumo).

QUÍMICOS:
    CIQ = Σⱼ Piqⱼ × Qiqⱼ , con Qiqⱼ = Σ(kg de los 12 meses).

Solo se calcula; las ENTRADAS las aporta la empresa (no se inventan).
"""
import csv
import io
from sqlalchemy import text

# --- Parámetros regulatorios del art. 2.1.2.1.3.4.6 (fijos; el 2.º segmento no devía) ---
UPSILON = {"acueducto": 9.8, "alcantarillado": 10.5}      # Υ (kN/m³): topes del peso unitario
ETA_ALCANTARILLADO = 0.60                                  # η mínimo de bombeo en alcantarillado
# η de acueducto por rango de volumen bombeado al año (límite superior, η):
ETA_ACUEDUCTO = [(1_000_000.0, 0.63), (3_000_000.0, 0.69), (float("inf"), 0.77)]
MESES_Q = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10", "m11", "m12"]


def _num(x):
    try:
        return float(x) if x is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def eta_de(servicio, volumen_m3):
    """η aplicable: 0,60 en alcantarillado; en acueducto según el volumen del punto."""
    if (servicio or "").lower().startswith("alcan"):
        return ETA_ALCANTARILLADO
    v = _num(volumen_m3)
    for lim, eta in ETA_ACUEDUCTO:
        if v <= lim:
            return eta
    return ETA_ACUEDUCTO[-1][1]


def calc_energia_punto(p):
    """Calcula un punto de energía a partir de sus entradas. Dos tipos (como el modelo):
      · 'bombeo'  : fórmula hidráulica — Keb = mín[(Υ/(3600·η))·V·H , Kr] ; Ceb = Keb·Pce.
      · 'otros'   : otros procesos operativos (p. ej. tratamiento) — Ce = Ko·Pce, sin eficiencia
                    (aquí `consumo_real_kwh` es Ko, el consumo real en kWh/año).
    Devuelve dict con FE, teórico, Keb, Ceb, costo_real y castigo por eficiencia."""
    serv = (p.get("servicio") or "acueducto").lower()
    tipo = (p.get("tipo") or "bombeo").lower()
    Kr = _num(p.get("consumo_real_kwh"))
    Pce = _num(p.get("precio_kwh"))
    if tipo.startswith("otro"):
        ceb = Kr * Pce
        return {"tipo": "otros", "upsilon": None, "eta": None, "fe": None, "teorico": None,
                "keb": Kr, "ceb": ceb, "costo_real": ceb, "castigo": 0.0}
    V = _num(p.get("volumen_m3"))
    H = _num(p.get("altura_m"))
    ups = UPSILON.get("alcantarillado" if serv.startswith("alcan") else "acueducto", 9.8)
    eta = eta_de(serv, V)
    fe = ups / (3600.0 * eta) if eta else 0.0           # kWh/(m³·m)
    teorico = fe * V * H                                  # consumo teórico (kWh)
    keb = min(teorico, Kr)                               # consumo eficiente (kWh)
    ceb = keb * Pce                                       # costo reconocido ($)
    costo_real = Kr * Pce
    castigo = max(0.0, costo_real - ceb)
    return {"tipo": "bombeo", "upsilon": ups, "eta": eta, "fe": fe, "teorico": teorico, "keb": keb,
            "ceb": ceb, "costo_real": costo_real, "castigo": castigo}


def calc_quimico_item(it):
    """CIQ de un insumo: precio_kg × suma de los 12 meses (kg)."""
    precio = _num(it.get("precio_kg"))
    cantidad = sum(_num(it.get(k)) for k in MESES_Q)
    return {"cantidad_anual": cantidad, "ciq": precio * cantidad}


# -------------------------------------------------------------------- lectura + totales
def energia_lista(conn, empresa_id, anio=None, servicio=None):
    """Energía agregada POR PUNTO (suma de los meses cargados). Cada entrada trae el cálculo anual
    (Ceb) y cuántos meses la componen. Para 'otros' el costo es Σ(Ko_m·Pce_m); para 'bombeo' se
    calcula sobre el volumen anual."""
    sql = ("SELECT id, anio, mes, servicio, tipo, no_sui, punto, actividad, volumen_m3, altura_m, "
           "consumo_real_kwh, precio_kwh, eta_reporte, origen, observacion "
           "FROM energia_punto WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " ORDER BY anio DESC, servicio, punto, mes"
    g = {}
    for r in conn.execute(text(sql), p).mappings().all():
        key = (r["anio"], r["servicio"], r["no_sui"], r["punto"])
        a = g.get(key)
        if a is None:
            a = g[key] = {"anio": r["anio"], "servicio": r["servicio"], "tipo": r["tipo"],
                          "no_sui": r["no_sui"], "punto": r["punto"], "actividad": r["actividad"],
                          "origen": r["origen"], "observacion": r["observacion"],
                          "vol": 0.0, "alt": None, "kwh": 0.0, "costo": 0.0, "psum": 0.0, "np": 0,
                          "meses": set(), "ids": []}
        a["ids"].append(r["id"])
        if r["mes"]:
            a["meses"].add(r["mes"])
        k = _num(r["consumo_real_kwh"]); pce = _num(r["precio_kwh"])
        a["vol"] += _num(r["volumen_m3"]); a["kwh"] += k
        if r["precio_kwh"] is not None:
            a["costo"] += k * pce; a["psum"] += pce; a["np"] += 1
        if r["altura_m"] is not None:
            a["alt"] = r["altura_m"] if a["alt"] is None else max(a["alt"], r["altura_m"])
    out = []
    for a in g.values():
        if a["kwh"] > 0 and a["costo"] > 0:
            pce = a["costo"] / a["kwh"]
        elif a["np"]:
            pce = a["psum"] / a["np"]
        else:
            pce = None
        d = {"anio": a["anio"], "servicio": a["servicio"], "tipo": a["tipo"], "no_sui": a["no_sui"],
             "punto": a["punto"], "actividad": a["actividad"], "origen": a["origen"],
             "observacion": a["observacion"], "volumen_m3": a["vol"] or None, "altura_m": a["alt"],
             "consumo_real_kwh": a["kwh"] or None, "precio_kwh": pce,
             "meses": sorted(a["meses"]), "n_meses": len(a["meses"]),
             "ids": a["ids"], "id": a["ids"][0] if a["ids"] else None}
        d["calc"] = calc_energia_punto(d)
        out.append(d)
    out.sort(key=lambda d: (-d["anio"], d["servicio"], d["punto"]))
    return out


def quimico_lista(conn, empresa_id, anio=None, servicio=None):
    cols = ", ".join(MESES_Q)
    sql = ("SELECT id, anio, servicio, no_sui, punto, insumo, estado, precio_kg, " + cols +
           ", origen, observacion FROM quimico_item WHERE empresa_id=:e")
    p = {"e": empresa_id}
    if anio:
        sql += " AND anio=:a"; p["a"] = anio
    if servicio:
        sql += " AND servicio=:s"; p["s"] = servicio
    sql += " ORDER BY anio DESC, servicio, punto, insumo"
    out = []
    for r in conn.execute(text(sql), p).mappings().all():
        d = dict(r)
        d["calc"] = calc_quimico_item(d)
        out.append(d)
    return out


def totales(conn, empresa_id, anio=None):
    """CE y CIQ reconocidos por (servicio, año): CE = ΣCeb ; CIQ = ΣCIQ. Para alimentar el CMO."""
    ce = {}
    for d in energia_lista(conn, empresa_id, anio=anio):
        k = (d["servicio"], d["anio"])
        a = ce.setdefault(k, {"ce": 0.0, "castigo": 0.0, "n": 0})
        a["ce"] += d["calc"]["ceb"]
        a["castigo"] += d["calc"]["castigo"]
        a["n"] += 1
    ciq = {}
    for d in quimico_lista(conn, empresa_id, anio=anio):
        k = (d["servicio"], d["anio"])
        a = ciq.setdefault(k, {"ciq": 0.0, "n": 0})
        a["ciq"] += d["calc"]["ciq"]
        a["n"] += 1
    return {"ce": ce, "ciq": ciq}


# -------------------------------------------------------------------- cargue (manual + masivo)
MES_HDR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# Energía: cargue POR MES (una fila por punto y mes). El sistema agrega al año base.
ENERGIA_HDR = ["anio", "mes", "servicio", "tipo", "no_sui", "punto", "actividad", "volumen_m3",
               "altura_m", "consumo_real_kwh", "precio_kwh"]
# Químicos: una fila por insumo y año; los kg van por mes (ene..dic).
QUIMICO_HDR = ["anio", "servicio", "no_sui", "punto", "insumo", "estado", "precio_kg"] + MES_HDR


def _pnum(s):
    """Número tolerante a formato colombiano: '1.000,88' -> 1000.88 ; '1000,5' -> 1000.5."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _pint(s):
    """Entero tolerante (año); None si vacío/ inválido."""
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


def _tipo(s):
    return "otros" if (s or "").strip().lower().startswith("otro") else "bombeo"


def energia_guardar(conn, empresa_id, anio, d, origen="empresa", cargado_por=None):
    """Inserta/actualiza un punto de energía para un MES (upsert por año+mes+servicio+no_sui+punto).
    mes = 0 = entrada anual/consolidada; 1..12 = mensual."""
    serv = _serv(d.get("servicio"))
    punto = (d.get("punto") or "").strip()
    if serv not in ("acueducto", "alcantarillado") or not punto:
        return None, "servicio y punto son obligatorios"
    mes = _pint(d.get("mes")) or 0
    mes = mes if 0 <= mes <= 12 else 0
    conn.execute(text(
        "INSERT INTO energia_punto(empresa_id,anio,mes,servicio,tipo,no_sui,punto,actividad,volumen_m3,"
        " altura_m,consumo_real_kwh,precio_kwh,eta_reporte,observacion,origen,cargado_por) "
        "VALUES (:e,:a,:m,:s,:t,:ns,:p,:ac,:v,:h,:k,:pc,:er,:ob,:og,:u) "
        "ON CONFLICT (empresa_id,anio,mes,servicio,no_sui,punto) DO UPDATE SET tipo=excluded.tipo, "
        "actividad=excluded.actividad, volumen_m3=excluded.volumen_m3, altura_m=excluded.altura_m, "
        "consumo_real_kwh=excluded.consumo_real_kwh, precio_kwh=excluded.precio_kwh, "
        "eta_reporte=excluded.eta_reporte, observacion=excluded.observacion, origen=excluded.origen, "
        "cargado_por=excluded.cargado_por, cargado_en=now()"),
        {"e": empresa_id, "a": int(anio), "m": mes, "s": serv, "t": _tipo(d.get("tipo")),
         "ns": (d.get("no_sui") or "").strip(), "p": punto, "ac": (d.get("actividad") or "").strip(),
         "v": _pnum(d.get("volumen_m3")), "h": _pnum(d.get("altura_m")),
         "k": _pnum(d.get("consumo_real_kwh")), "pc": _pnum(d.get("precio_kwh")),
         "er": _pnum(d.get("eta_reporte")), "ob": (d.get("observacion") or "").strip() or None,
         "og": origen, "u": cargado_por})
    return True, None


def quimico_guardar(conn, empresa_id, anio, d, origen="empresa", cargado_por=None):
    serv = _serv(d.get("servicio"))
    insumo = (d.get("insumo") or "").strip()
    if serv not in ("acueducto", "alcantarillado") or not insumo:
        return None, "servicio e insumo son obligatorios"
    meses = {f"m{i+1}": _pnum(d.get(MES_HDR[i])) or 0.0 for i in range(12)}
    sets = ", ".join(f"m{i+1}=excluded.m{i+1}" for i in range(12))
    conn.execute(text(
        "INSERT INTO quimico_item(empresa_id,anio,servicio,no_sui,punto,insumo,estado,precio_kg,"
        " m1,m2,m3,m4,m5,m6,m7,m8,m9,m10,m11,m12,observacion,origen,cargado_por) "
        "VALUES (:e,:a,:s,:ns,:p,:in,:es,:pk,:m1,:m2,:m3,:m4,:m5,:m6,:m7,:m8,:m9,:m10,:m11,:m12,:ob,:og,:u) "
        "ON CONFLICT (empresa_id,anio,servicio,punto,insumo) DO UPDATE SET estado=excluded.estado, "
        "no_sui=excluded.no_sui, precio_kg=excluded.precio_kg, " + sets + ", observacion=excluded.observacion, "
        "origen=excluded.origen, cargado_por=excluded.cargado_por, cargado_en=now()"),
        {"e": empresa_id, "a": int(anio), "s": serv, "ns": (d.get("no_sui") or "").strip(),
         "p": (d.get("punto") or "").strip(), "in": insumo, "es": (d.get("estado") or "").strip(),
         "pk": _pnum(d.get("precio_kg")), "ob": (d.get("observacion") or "").strip() or None,
         "og": origen, "u": cargado_por, **meses})
    return True, None


def energia_masivo(conn, empresa_id, anio, texto, cargado_por=None):
    """Cargue masivo de energía POR MES (una fila por punto y mes). Guarda cada fila tal cual, SIN
    borrar el resto del año: solo reemplaza las combinaciones (año, mes) presentes en el archivo. Así:
      · un archivo con los 12 meses reemplaza el año completo;
      · un archivo de un solo mes reemplaza SOLO ese mes (los demás meses se conservan).
    Si una fila no trae `mes`, es modo ANUAL (mes=0) y reemplaza todo el año. La CE de cada punto es
    la suma de sus meses (se calcula en `energia_lista`). Devuelve (n_filas, errores)."""
    filas = _leer_csv(texto)
    datos, err = [], []
    anios_anual = set()      # años cargados en modo anual (sin columna mes) → reemplaza todo el año
    combos = set()           # (año, mes) mensuales a reemplazar
    for i, r in enumerate(filas, start=2):
        if not any((r.get(c) or "").strip() for c in ENERGIA_HDR):
            continue
        a = _pint(r.get("anio")) or int(anio)
        m = _pint(r.get("mes")) or 0
        serv = _serv(r.get("servicio"))
        punto = (r.get("punto") or "").strip()
        if serv not in ("acueducto", "alcantarillado") or not punto:
            err.append(f"fila {i}: servicio y punto son obligatorios")
            continue
        datos.append((a, m, serv, r))
        if m:
            combos.add((a, m))
        else:
            anios_anual.add(a)
    # Borrado selectivo: modo anual borra el año entero; modo mensual borra solo ese (año, mes)
    # y además limpia una posible entrada anual (mes=0) de ese año (lo mensual sustituye a lo anual).
    for a in anios_anual:
        conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=:e AND anio=:a"), {"e": empresa_id, "a": a})
    for a in {x for (x, _) in combos} - anios_anual:
        conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=:e AND anio=:a AND mes=0"),
                     {"e": empresa_id, "a": a})
    for (a, m) in combos:
        if a in anios_anual:
            continue
        conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=:e AND anio=:a AND mes=:m"),
                     {"e": empresa_id, "a": a, "m": m})
    n = 0
    for (a, m, serv, r) in datos:
        d = {"servicio": serv, "tipo": r.get("tipo"), "no_sui": r.get("no_sui"), "punto": r.get("punto"),
             "actividad": r.get("actividad"), "volumen_m3": r.get("volumen_m3"), "altura_m": r.get("altura_m"),
             "consumo_real_kwh": r.get("consumo_real_kwh"), "precio_kwh": r.get("precio_kwh"), "mes": m}
        ok, e = energia_guardar(conn, empresa_id, a, d, origen="masivo", cargado_por=cargado_por)
        if ok:
            n += 1
        else:
            err.append(f"{r.get('punto')}: {e}")
    return n, err


def quimico_masivo(conn, empresa_id, anio, texto, cargado_por=None):
    """Cargue masivo de químicos: una fila por insumo y año (kg por mes). Toma el año de la columna
    `anio` (si falta, el del selector) y reemplaza cada año presente."""
    filas = _leer_csv(texto)
    anios = {(_pint(r.get("anio")) or int(anio)) for r in filas if (r.get("insumo") or "").strip()}
    for a in anios:
        conn.execute(text("DELETE FROM quimico_item WHERE empresa_id=:e AND anio=:a"), {"e": empresa_id, "a": a})
    n, err = 0, []
    for i, r in enumerate(filas, start=2):
        a = _pint(r.get("anio")) or int(anio)
        ok, e = quimico_guardar(conn, empresa_id, a, r, origen="masivo", cargado_por=cargado_por)
        if ok:
            n += 1
        elif any((r.get(c) or "").strip() for c in QUIMICO_HDR):
            err.append(f"fila {i}: {e}")
    return n, err


def energia_eliminar(conn, empresa_id, pid):
    """Elimina el PUNTO completo (todos sus meses) al que pertenece esa fila."""
    row = conn.execute(text("SELECT anio, servicio, no_sui, punto FROM energia_punto "
                            "WHERE empresa_id=:e AND id=:i"), {"e": empresa_id, "i": int(pid)}).mappings().first()
    if not row:
        return
    conn.execute(text("DELETE FROM energia_punto WHERE empresa_id=:e AND anio=:a AND servicio=:s "
                      "AND no_sui=:n AND punto=:p"),
                 {"e": empresa_id, "a": row["anio"], "s": row["servicio"], "n": row["no_sui"], "p": row["punto"]})


def energia_detalle_mes(conn, empresa_id, anio, servicio, no_sui, punto):
    """Detalle por mes de un punto (para auditar la suma anual)."""
    return [dict(r) for r in conn.execute(text(
        "SELECT mes, consumo_real_kwh, precio_kwh, volumen_m3, altura_m FROM energia_punto "
        "WHERE empresa_id=:e AND anio=:a AND servicio=:s AND no_sui=:n AND punto=:p ORDER BY mes"),
        {"e": empresa_id, "a": anio, "s": servicio, "n": no_sui, "p": punto}).mappings().all()]


def quimico_eliminar(conn, empresa_id, qid):
    conn.execute(text("DELETE FROM quimico_item WHERE empresa_id=:e AND id=:i"), {"e": empresa_id, "i": int(qid)})


def plantilla_energia():
    # Una fila por punto y mes; el sistema suma los meses al año base.
    ej = ["2024,1,acueducto,otros,15575,PTAP El Roble,producción,,,98085,1011.47",
          "2024,2,acueducto,otros,15575,PTAP El Roble,producción,,,95120,1015.30",
          "2024,1,acueducto,bombeo,5635,17 de diciembre,distribución,57688,65,62004,1000.88"]
    return "plantilla_energia.csv", ",".join(ENERGIA_HDR) + "\n" + "\n".join(ej) + "\n"


def plantilla_quimico():
    ej = ["2024,acueducto,15575,PTAP El Roble,Cloro,gaseoso,6214.18,2522,2474,2580,2432,2723,2442,2846,2824,2350,2215,2064,3154"]
    return "plantilla_quimicos.csv", ",".join(QUIMICO_HDR) + "\n" + "\n".join(ej) + "\n"


def ce_ciq_de(conn, empresa_id, servicio, anio):
    """CE y CIQ reconocidos (ΣCeb, ΣCIQ) de un servicio y año, o (None, None) si no hay módulo
    cargado (para que el motor use el valor del balance como respaldo)."""
    serv = (servicio or "").lower()
    ce = conn.execute(text(
        "SELECT count(*) FROM energia_punto WHERE empresa_id=:e AND anio=:a AND servicio=:s"),
        {"e": empresa_id, "a": anio, "s": serv}).scalar()
    ciq = conn.execute(text(
        "SELECT count(*) FROM quimico_item WHERE empresa_id=:e AND anio=:a AND servicio=:s"),
        {"e": empresa_id, "a": anio, "s": serv}).scalar()
    t = totales(conn, empresa_id, anio=anio)
    ce_val = t["ce"].get((serv, anio), {}).get("ce") if ce else None
    ciq_val = t["ciq"].get((serv, anio), {}).get("ciq") if ciq else None
    return ce_val, ciq_val
