# -*- coding: utf-8 -*-
"""Módulo de Inversiones / POIR — registro de proyectos y seguimiento del avance.

Cada proyecto se crea **planeado** (presupuesto y fecha planeada de entrada en operación) y se
le registra el **avance físico (%)** y **financiero ($ ejecutado acumulado)** por corte, hasta la
**fecha real de entrada en operación**. La **clasificación** distingue si el proyecto está asociado
al **CMI_POIR** (opera desde 2027; art. 2.1.2.1.3.5.14) o se reconoce **expost** con la fórmula
general (art. 2.1.2.1.3.5). En el período de inicio solo se registra y hace seguimiento: la base
alimenta el primer recálculo y la verificación del 80 % de ejecución del POIR para entrar a la BCR₀.
"""
from sqlalchemy import text

CLASIFICACIONES = {"CMI_POIR": "Asociado al CMI_POIR (desde 2027)",
                   "expost_general": "Reconocimiento expost (fórmula general)"}
ESTADOS = {"planeado": "Planeado", "en_ejecucion": "En ejecución",
           "en_operacion": "En operación", "suspendido": "Suspendido"}
COMPONENTES_AC = ["captación", "aducción", "conducción", "tratamiento",
                  "almacenamiento", "distribución", "macromedición", "otro"]
COMPONENTES_AL = ["recolección", "transporte", "tratamiento de aguas residuales",
                  "bombeo", "otro"]
UMBRAL_POIR = 0.80   # 80 % de ejecución para entrar a la BCR₀ (art. 2.1.2.1.3.5.14)


def _norm_serv(s):
    s = (s or "").strip().lower()
    if s.startswith("ac"):
        return "acueducto"
    if s.startswith("al"):
        return "alcantarillado"
    return None


def crear_proyecto(conn, empresa_id, d):
    """Crea o actualiza un proyecto (upsert por código POIR). `d` es un dict de campos."""
    serv = _norm_serv(d.get("servicio"))
    if not serv:
        return None, "servicio inválido"
    clasif = (d.get("clasificacion") or "CMI_POIR").strip()
    if clasif not in CLASIFICACIONES:
        return None, "clasificación inválida"
    origen = (d.get("origen") or "POIR_nuevo").strip()
    marco = (d.get("marco") or "688").strip()
    if marco not in ("688", "1032"):
        marco = "688"
    row = conn.execute(text(
        "INSERT INTO proyecto_inversion(empresa_id,codigo_poir,nombre,servicio,aps,"
        " componente_sistema,meta_asociada,clasificacion,origen,marco,valor_planeado,"
        " fecha_planeada_operacion,via688,vp_recaudo,vida_util,observacion,creado_por) "
        "VALUES (:e,:cod,:nom,:s,:aps,:comp,:meta,:cl,:org,:marco,:vp,:fpo,:via,:vpr,:vu,:obs,:u) "
        "ON CONFLICT (empresa_id,codigo_poir) DO UPDATE SET "
        " nombre=excluded.nombre, servicio=excluded.servicio, aps=excluded.aps, "
        " componente_sistema=excluded.componente_sistema, meta_asociada=excluded.meta_asociada, "
        " clasificacion=excluded.clasificacion, origen=excluded.origen, marco=excluded.marco, "
        " valor_planeado=excluded.valor_planeado, "
        " fecha_planeada_operacion=excluded.fecha_planeada_operacion, via688=excluded.via688, "
        " vp_recaudo=excluded.vp_recaudo, vida_util=excluded.vida_util, "
        " observacion=excluded.observacion, actualizado_en=now() "
        "RETURNING id"),
        {"e": empresa_id, "cod": (d.get("codigo_poir") or "").strip(),
         "nom": (d.get("nombre") or "").strip(), "s": serv, "aps": d.get("aps"),
         "comp": d.get("componente_sistema"), "meta": d.get("meta_asociada"),
         "cl": clasif, "org": origen, "marco": marco, "vp": d.get("valor_planeado"),
         "fpo": d.get("fecha_planeada_operacion"), "via": d.get("via688"),
         "vpr": d.get("vp_recaudo"), "vu": d.get("vida_util"),
         "obs": d.get("observacion"), "u": d.get("creado_por")}).scalar()
    return row, None


def _estado(fisico, financiero, planeado, fecha_real):
    if fecha_real or (fisico is not None and fisico >= 100):
        return "en_operacion"
    if (fisico and fisico > 0) or (financiero and financiero > 0):
        return "en_ejecucion"
    return "planeado"


def registrar_avance(conn, empresa_id, proyecto_id, anio, mes, fisico, financiero,
                     observacion=None, fecha_real=None, cargado_por=None):
    """Registra el avance de un corte y actualiza el estado del proyecto."""
    p = conn.execute(text(
        "SELECT valor_planeado, estado FROM proyecto_inversion WHERE id=:p AND empresa_id=:e"),
        {"p": proyecto_id, "e": empresa_id}).mappings().first()
    if not p:
        return False, "proyecto no disponible"
    conn.execute(text(
        "INSERT INTO avance_inversion(empresa_id,proyecto_id,anio,mes,avance_fisico,"
        " avance_financiero,observacion,cargado_por) VALUES (:e,:p,:a,:m,:f,:fi,:o,:u) "
        "ON CONFLICT (empresa_id,proyecto_id,anio,mes) DO UPDATE SET "
        " avance_fisico=excluded.avance_fisico, avance_financiero=excluded.avance_financiero, "
        " observacion=excluded.observacion, cargado_por=excluded.cargado_por, cargado_en=now()"),
        {"e": empresa_id, "p": proyecto_id, "a": anio, "m": mes, "f": fisico,
         "fi": financiero, "o": observacion, "u": cargado_por})
    est = p["estado"]
    if est != "suspendido":
        nuevo = _estado(fisico, financiero, p["valor_planeado"], fecha_real)
        sets = "estado=:st, actualizado_en=now()"
        params = {"p": proyecto_id, "e": empresa_id, "st": nuevo}
        if fecha_real or (fisico is not None and fisico >= 100):
            if fecha_real:
                sets += ", fecha_real_operacion=:fr"
                params["fr"] = fecha_real
        conn.execute(text(f"UPDATE proyecto_inversion SET {sets} WHERE id=:p AND empresa_id=:e"),
                     params)
    return True, None


def tablero(conn, empresa_id, marco=None):
    """Proyectos con su último avance y el % de ejecución financiera.
    `marco` opcional ('688'/'1032') limita al POIR de ese marco; None = todos."""
    p = {"e": empresa_id}
    filtro = ""
    if marco:
        filtro = " AND p.marco=:marco"; p["marco"] = marco
    rows = conn.execute(text(
        "SELECT p.*, "
        " a.anio AS corte_anio, a.mes AS corte_mes, a.avance_fisico, a.avance_financiero "
        "FROM proyecto_inversion p "
        "LEFT JOIN LATERAL ("
        "  SELECT anio, mes, avance_fisico, avance_financiero FROM avance_inversion "
        "  WHERE proyecto_id=p.id ORDER BY anio DESC, mes DESC LIMIT 1) a ON true "
        "WHERE p.empresa_id=:e" + filtro + " ORDER BY p.servicio, p.codigo_poir"),
        p).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        vp = r["valor_planeado"] or 0.0
        fin = r["avance_financiero"] or 0.0
        d["pct_financiero"] = (fin / vp * 100.0) if vp else None
        out.append(d)
    return out


def resumen(conn, empresa_id, marco=None):
    """Totales por clasificación, por estado, % de ejecución global y chequeo del 80 % por servicio."""
    proys = tablero(conn, empresa_id, marco=marco)
    por_clasif = {}
    por_estado = {}
    por_servicio = {}
    tot_plan = tot_ejec = 0.0
    for p in proys:
        vp = p["valor_planeado"] or 0.0
        fin = p["avance_financiero"] or 0.0
        tot_plan += vp
        tot_ejec += fin
        c = por_clasif.setdefault(p["clasificacion"], {"n": 0, "planeado": 0.0, "ejecutado": 0.0})
        c["n"] += 1; c["planeado"] += vp; c["ejecutado"] += fin
        e = por_estado.setdefault(p["estado"], 0)
        por_estado[p["estado"]] = e + 1
        s = por_servicio.setdefault(p["servicio"], {"planeado": 0.0, "ejecutado": 0.0})
        s["planeado"] += vp; s["ejecutado"] += fin
    for s, d in por_servicio.items():
        d["pct"] = (d["ejecutado"] / d["planeado"] * 100.0) if d["planeado"] else None
        d["supera_80"] = (d["pct"] is not None and d["pct"] >= UMBRAL_POIR * 100.0)
    return {"n": len(proys), "tot_plan": tot_plan, "tot_ejec": tot_ejec,
            "pct_global": (tot_ejec / tot_plan * 100.0) if tot_plan else None,
            "por_clasif": por_clasif, "por_estado": por_estado, "por_servicio": por_servicio}
