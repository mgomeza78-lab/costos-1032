# -*- coding: utf-8 -*-
"""Vista del Balance de Prueba clasificado (Res. CRA 1032).

Por COMPONENTE (CMA / CMO / CMICT, selector), el desglose por SUBCOMPONENTE y por AÑO base cargado,
mostrando en cada año tres columnas: Acueducto, Alcantarillado y Ac + Al. La clase 5 (CMA e impuestos
administrativos) se reparte por un % Ac/Al editable; la clase 7 (CMO) va al servicio de cada cuenta.
Al tocar un subcomponente se despliega el detalle de CUENTAS con valor (numerador_cuenta). Además, una
tabla aparte con los conceptos EXCLUIDOS (no reconocidos / que migran a otro componente).
Fuentes: `numerador_subcomp` (agregado) y `numerador_cuenta` (detalle). Período = año (saldo acumulado)."""
from sqlalchemy import text
from ingesta import get_pct_ac

COMPONENTES = ["CMA", "CMO", "CMICT"]
COMP_NOMBRE = {"CMA": "Costo Medio de Administración", "CMO": "Costo Medio de Operación",
               "CMICT": "Costo Medio de Impuestos, Contribuciones y Tasas"}
ART = {"CMA": "2.1.2.1.3.2.4", "CMO": "2.1.2.1.3.4.4", "CMICT": "2.1.2.1.3.6"}
SUBCOMP_LABEL = {
    "CAC-1": "Beneficios a empleados (admin.)",
    "CAC-2": "Costos generales (admin.)",
    "CAC-2.COM": "Comercialización (lectura y entrega de facturas)",
    "CAC-3": "Otros administrativos reconocidos",
    "COC-1": "Beneficios a empleados (operación)",
    "COC-2": "Costos generales (operación)",
    "COC-3": "Operativos (grupo 3)", "COC-4": "Tratamiento de aguas residuales",
    "COC-5": "Operación FNCER",
    "CE": "Energía (costo particular)",
    "CIQ": "Insumos químicos (costo particular)",
    "COIR": "Inversiones ambientales y gestión del riesgo",
    "ICTA": "Impuestos y contribuciones (ICTA)",
    "ICTO": "Impuestos operativos (ICTO)",
    "TA": "Tasas ambientales (TUA / retributiva)",
    # Excluidos
    "CAC-X": "Administrativos NO reconocidos",
    "COC-X": "Operativos NO reconocidos",
    "ICT-X": "Impuestos NO reconocidos",
    "DEP": "Depreciaciones (se remuneran en el CMI)",
    "NT": "No tarifario / financiero",
    "CIAO": "Activos admin./oper. (migran al CMI)",
    "CII": "Inversiones (migran al CMI)",
}


# Ajustes manuales: numerales del CAC que la contabilidad no separa (art. 2.1.2.1.3.2.4) y
# exclusiones explícitas (art. 2.1.2.1.3.3.3). Conceptos guiados por la 1032 (+ 'Otro' libre).
TIPOS_CAC = ["CAC-4", "CAC-5", "CAC-6"]
TIPO_LABEL = {
    "CAC-4": "Gestión social — PQRS y Comités",
    "CAC-5": "Iniciativas de gestión social (IDH7/IDH14)",
    "CAC-6": "Inversiones ambientales administrativas",
}
ART_MANUAL = {"CAC-4": "2.1.2.1.3.2.4 num. 4", "CAC-5": "2.1.2.1.3.2.4 num. 5",
              "CAC-6": "2.1.2.1.3.2.4 num. 6", "exclusion": "2.1.2.1.3.3.3"}
CONCEPTOS_MANUAL = {
    "CAC-4": ["PQRS", "Comités de Desarrollo y Control Social"],
    "CAC-5": ["Esquemas diferenciales urbanos (lit. a)",
              "Fortalecimiento de la participación comunitaria (lit. b)",
              "Sensibilización, comunicación y capacitación (lit. c)",
              "Estrategias innovadoras (lit. d)"],
    "CAC-6": ["Inversiones ambientales administrativas"],
    "exclusion": ["Costos con ingreso asociado",
                  "Actividades no reguladas o complementarias",
                  "Donaciones",
                  "Multas, sanciones e intereses de mora",
                  "Publicidad / propaganda no obligatoria"],
}


def _celda(r, pct):
    ac = (r["ac_dir"] or 0.0) + (r["repartir"] or 0.0) * pct
    al = (r["al_dir"] or 0.0) + (r["repartir"] or 0.0) * (1.0 - pct)
    return ac, al


def _cols(get_ac_al, anios, acc=None):
    """Arma {anio: {ac, al, suma}} y la suma de años; `get_ac_al(anio)` -> (ac, al). `acc` acumula
    el total por año (lista [ac, al]) si se pasa."""
    cols = {}
    s_ac = s_al = 0.0
    for a in anios:
        ac, al = get_ac_al(a)
        cols[a] = {"ac": ac, "al": al, "suma": ac + al}
        s_ac += ac
        s_al += al
        if acc is not None:
            acc[a][0] += ac
            acc[a][1] += al
    return cols, {"ac": s_ac, "al": s_al, "suma": s_ac + s_al}


def _tabla(conn, empresa_id, componente, anios, pct):
    """Tabla de un componente: subcomponentes (con detalle de cuentas) + total, por año (Ac/Al/Ac+Al)."""
    subs = {}
    for r in conn.execute(text(
        "SELECT anio, subcomponente, ac_dir, al_dir, repartir FROM numerador_subcomp "
        "WHERE empresa_id=:e AND componente=:c AND cod_dane='' ORDER BY subcomponente, anio"),
            {"e": empresa_id, "c": componente}).mappings().all():
        subs.setdefault(r["subcomponente"], {})[r["anio"]] = _celda(r, pct)
    det = {}
    for r in conn.execute(text(
        "SELECT anio, subcomponente, codigo, nombre, ac_dir, al_dir, repartir FROM numerador_cuenta "
        "WHERE empresa_id=:e AND componente=:c AND cod_dane='' ORDER BY subcomponente, codigo, anio"),
            {"e": empresa_id, "c": componente}).mappings().all():
        d = det.setdefault(r["subcomponente"], {}).setdefault(
            r["codigo"], {"nombre": r["nombre"], "anio": {}})
        d["anio"][r["anio"]] = _celda(r, pct)

    acc = {a: [0.0, 0.0] for a in anios}
    filas = []
    for sc in sorted(subs):
        cols, suma = _cols(lambda a, sc=sc: subs[sc].get(a, (0.0, 0.0)), anios, acc)
        detalle = []
        for codigo in sorted(det.get(sc, {}), key=lambda c: (det[sc][c]["nombre"] or c)):
            dd = det[sc][codigo]
            dcols, dsuma = _cols(lambda a, dd=dd: dd["anio"].get(a, (0.0, 0.0)), anios)
            detalle.append({"codigo": codigo, "nombre": dd["nombre"], "cols": dcols, "suma": dsuma})
        filas.append({"sub": sc, "nombre": SUBCOMP_LABEL.get(sc, sc), "cols": cols,
                      "suma": suma, "detalle": detalle})
    total = {a: {"ac": acc[a][0], "al": acc[a][1], "suma": acc[a][0] + acc[a][1]} for a in anios}
    total_suma = {"ac": sum(acc[a][0] for a in anios), "al": sum(acc[a][1] for a in anios),
                  "suma": sum(acc[a][0] + acc[a][1] for a in anios)}
    return {"filas": filas, "total": total, "total_suma": total_suma, "hay": bool(subs)}


def _ajuste_filas(items, anios, label_fn, detalle=True):
    """Arma {filas, total, total_suma} (forma de `_tabla`) desde items=[(clave, grupo)], con
    grupo = {'anio': {a:[ac,al]}, 'det': {concepto: {a:[ac,al]}}}."""
    acc = {a: [0.0, 0.0] for a in anios}
    filas = []
    for clave, g in items:
        cols, suma = _cols(lambda a, g=g: tuple(g["anio"].get(a, [0.0, 0.0])), anios, acc)
        det = []
        if detalle:
            for cc in sorted(g["det"]):
                dd = g["det"][cc]
                dcols, dsuma = _cols(lambda a, dd=dd: tuple(dd.get(a, [0.0, 0.0])), anios)
                det.append({"codigo": "", "nombre": cc, "cols": dcols, "suma": dsuma})
        filas.append({"sub": clave, "nombre": label_fn(clave), "cols": cols, "suma": suma, "detalle": det})
    total = {a: {"ac": acc[a][0], "al": acc[a][1], "suma": acc[a][0] + acc[a][1]} for a in anios}
    total_suma = {"ac": sum(acc[a][0] for a in anios), "al": sum(acc[a][1] for a in anios),
                  "suma": sum(acc[a][0] + acc[a][1] for a in anios)}
    return {"filas": filas, "total": total, "total_suma": total_suma}


def _agrupar(rows, claves_fijas, clave_de, anios, pct):
    grupos = {}
    orden = list(claves_fijas)
    for k in claves_fijas:
        grupos[k] = {"anio": {a: [0.0, 0.0] for a in anios}, "det": {}}
    for r in rows:
        ac, al = _celda(r, pct)
        k = clave_de(r)
        if k not in grupos:
            grupos[k] = {"anio": {a: [0.0, 0.0] for a in anios}, "det": {}}
            orden.append(k)
        grupos[k]["anio"].setdefault(r["anio"], [0.0, 0.0])
        grupos[k]["anio"][r["anio"]][0] += ac
        grupos[k]["anio"][r["anio"]][1] += al
        d = grupos[k]["det"].setdefault(r["concepto"], {})
        d.setdefault(r["anio"], [0.0, 0.0])
        d[r["anio"]][0] += ac
        d[r["anio"]][1] += al
    return [(k, grupos[k]) for k in orden]


def _desagregacion(conn, empresa_id, anios, pct):
    rows = conn.execute(text(
        "SELECT anio, tipo, concepto, ac_dir, al_dir, repartir FROM balance_ajuste "
        "WHERE empresa_id=:e AND tipo = ANY(:tt) AND cod_dane='' ORDER BY tipo, concepto, anio"),
        {"e": empresa_id, "tt": TIPOS_CAC}).mappings().all()
    items = _agrupar(rows, TIPOS_CAC, lambda r: r["tipo"], anios, pct)
    out = _ajuste_filas(items, anios, lambda t: TIPO_LABEL.get(t, t), detalle=True)
    out["hay"] = bool(rows)
    return out


def _exclusiones(conn, empresa_id, componente, anios, pct):
    rows = conn.execute(text(
        "SELECT anio, concepto, ac_dir, al_dir, repartir FROM balance_ajuste "
        "WHERE empresa_id=:e AND tipo='exclusion' AND componente=:c AND cod_dane='' "
        "ORDER BY concepto, anio"), {"e": empresa_id, "c": componente}).mappings().all()
    items = _agrupar(rows, [], lambda r: r["concepto"], anios, pct)
    out = _ajuste_filas(items, anios, lambda c: c, detalle=False)
    out["hay"] = bool(rows)
    return out


def resumen(conn, empresa_id, componente=None):
    pct = get_pct_ac(conn, empresa_id)
    anios = [r[0] for r in conn.execute(text(
        "SELECT anio FROM numerador_subcomp WHERE empresa_id=:e "
        "UNION SELECT anio FROM balance_ajuste WHERE empresa_id=:e ORDER BY anio"),
        {"e": empresa_id}).all()]
    comp_sel = componente if componente in COMPONENTES else "CMA"
    principal = _tabla(conn, empresa_id, comp_sel, anios, pct)
    excluido = _tabla(conn, empresa_id, "Excluido", anios, pct)
    desagregacion = _desagregacion(conn, empresa_id, anios, pct)        # CAC-4/5/6 (informativo)
    exclusiones = _exclusiones(conn, empresa_id, comp_sel, anios, pct)   # se restan del numerador
    neto = {a: {"ac": principal["total"][a]["ac"] - exclusiones["total"][a]["ac"],
                "al": principal["total"][a]["al"] - exclusiones["total"][a]["al"],
                "suma": principal["total"][a]["suma"] - exclusiones["total"][a]["suma"]} for a in anios}
    return {"componentes": COMPONENTES, "comp_nombre": COMP_NOMBRE, "componente": comp_sel,
            "anios": anios, "pct_ac": pct, "pct_al": 1.0 - pct,
            "usa_pct": comp_sel in ("CMA", "CMICT"), "principal": principal, "excluido": excluido,
            "desagregacion": desagregacion, "exclusiones": exclusiones, "neto": neto,
            "hay_datos": bool(anios), "art": ART.get(comp_sel, ""), "art_manual": ART_MANUAL}
