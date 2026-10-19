# -*- coding: utf-8 -*-
"""Apertura del numerador por numerales — CAC, COC, CMI y CMICT (Res. CRA 1032).

Codifica la taxonomía de subcomponentes de la Resolución CRA 1032 de 2026
(arts. 2.1.2.1.3.2.4 para el CAC, 2.1.2.1.3.4.4 para el COC, 2.1.2.1.3.5 para el
CMI y 2.1.2.1.3.6 para el CMICT) y carga la clasificación real de Las Ceibas
tomada del «Maestro de Codificación Contable CRA 1032» (hoja Cruce_PlanCuentas,
276 cuentas), reconciliada contra su hoja Resumen_Control. No se inventa ninguna
cifra: todas provienen del Maestro del prestador.

Hallazgos de la clasificación (ver README_numerador):
 1. El Maestro clasifica por SUBCOMPONENTE; el reparto por servicio (AC/AL) es un
    paso posterior (driver de reparto del Modelo completo), no está en el cruce.
 2. CE y CIQ RECONOCIDOS no salen del balance: se construyen con la fórmula de
    costos particulares (art. 2.1.2.1.3.4.6/.7). La energía contable queda
    clasificada en CE solo para que el balance cuadre; el CIQ del balance es 0
    (los químicos vienen de los certificados / reporte CUP).
 3. Traslado de la clase 7 al CMA (sufijo .COM): gastos de comercialización
    —toma de lectura, facturación— que el num. 2 del art. 2.1.2.1.3.2.4 reconoce
    en el CAC y el num. 2 del art. 2.1.2.1.3.4.4 excluye del COC.
 4. Las listas de impuestos son taxativas: lo no reconocido va a ICT-X (Excluido),
    no al CMICT (p. ej. impuesto de vehículos, estampillas, intereses de mora).
"""
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Subcomp:
    cod: str
    nombre: str
    componente: str   # CMA / CMO / CMI / CMICT / Excluido
    numeral: str      # artículo y numeral
    puntaje: str      # tratamiento en el puntaje de eficiencia
    tabla: str = ""


# ── Taxonomía normativa (nivel 2 del código del Maestro) ──
TAXONOMIA = [
    Subcomp("CAC-1", "Beneficios a empleados administrativos", "CMA", "2.1.2.1.3.2.4 num.1", "Ordinario (PE_ADMIN)", "1.a/1.b"),
    Subcomp("CAC-1.COM", "↳ Beneficios del personal comercial", "CMA", "2.1.2.1.3.2.4 num.1", "Ordinario (PE_ADMIN)", "1.a/1.b"),
    Subcomp("CAC-2", "Costos generales administrativos (incl. gastos de comercialización)", "CMA", "2.1.2.1.3.2.4 num.2", "Ordinario (PE_ADMIN)", "1.c/1.d"),
    Subcomp("CAC-2.COM", "↳ Gastos de comercialización trasladados (lectura, facturación)", "CMA", "2.1.2.1.3.2.4 num.2", "Ordinario (PE_ADMIN)", "1.c/1.d"),
    Subcomp("CAC-3", "Amortizaciones administrativas", "CMA", "2.1.2.1.3.2.4 num.3", "Ordinario (PE_ADMIN)", "1.e/1.f"),
    Subcomp("CAC-4", "Costos generales de gestión social (PQRS y Comités)", "CMA", "2.1.2.1.3.2.4 num.4", "Ordinario (PE_ADMIN)", "1.g"),
    Subcomp("CAC-4.COM", "↳ PQRS y Comités trasladados de la clase 7", "CMA", "2.1.2.1.3.2.4 num.4", "Ordinario (PE_ADMIN)", "1.g"),
    Subcomp("CAC-5", "Costos de iniciativas de gestión social", "CMA", "2.1.2.1.3.2.4 num.5", "PARTICULAR (PE_ADMIN)", "1.h"),
    Subcomp("CAC-6", "Costos administrativos de inversiones ambientales", "CMA", "2.1.2.1.3.2.4 num.6", "Ordinario (PE_ADMIN)", "1.i"),
    Subcomp("COC-1", "Beneficios a empleados operativos", "CMO", "2.1.2.1.3.4.4 num.1", "Ordinario (PE_OPER)", "2.a/2.b"),
    Subcomp("COC-2", "Costos generales operativos", "CMO", "2.1.2.1.3.4.4 num.2", "Ordinario (PE_OPER)", "2.c/2.d"),
    Subcomp("COC-3", "Amortizaciones operativas", "CMO", "2.1.2.1.3.4.4 num.3", "Ordinario (PE_OPER)", "2.e/2.f"),
    Subcomp("COC-4", "Tratamiento de aguas residuales", "CMO", "2.1.2.1.3.4.4 num.4", "PARTICULAR (PE_OPER)", "2.g"),
    Subcomp("COC-5", "Operación de FNCER", "CMO", "2.1.2.1.3.4.4 num.5", "PARTICULAR (PE_OPER)", "2.h"),
    Subcomp("CE", "Costo particular de energía (reconocido = build eficiente)", "CMO", "2.1.2.1.3.4.6", "No pasa por puntaje", ""),
    Subcomp("CIQ", "Costo particular de insumos químicos (reconocido = reporte CUP)", "CMO", "2.1.2.1.3.4.7", "No pasa por puntaje", ""),
    Subcomp("COIR", "Costo operativo de inversiones ambientales (COIR)", "CMO", "2.1.2.1.3.4.8", "No pasa por puntaje", ""),
    Subcomp("CII", "Costo de inversión en infraestructura", "CMI", "2.1.2.1.3.5", "No aplica", ""),
    Subcomp("CIAR", "Costo de inversión ambiental y de gestión del riesgo", "CMI", "2.1.2.1.3.5", "No aplica", ""),
    Subcomp("CIAO", "Costo de inversión en activos administrativos/operativos", "CMI", "2.1.2.1.3.5", "No aplica", ""),
    Subcomp("ICTA", "Impuestos, contribuciones y tasas administrativas", "CMICT", "2.1.2.1.3.6", "No aplica", ""),
    Subcomp("ICTO", "Impuestos, contribuciones y tasas operativas", "CMICT", "2.1.2.1.3.6", "No aplica", ""),
    Subcomp("TA", "Tasas ambientales — uso del agua y retributiva", "CMICT", "2.1.2.1.3.6", "No aplica", ""),
    Subcomp("DEP", "Depreciaciones, provisiones y deterioro", "Excluido", "Anexo / exclusión", "Excluido", ""),
    Subcomp("CAC-X", "Costos administrativos NO reconocidos", "Excluido", "Anexo / exclusión", "Excluido", ""),
    Subcomp("COC-X", "Costos operativos NO reconocidos", "Excluido", "Anexo / exclusión", "Excluido", ""),
    Subcomp("ICT-X", "Impuestos y contribuciones excluidos (lista taxativa)", "Excluido", "Anexo / exclusión", "Excluido", ""),
    Subcomp("NT", "No tarifario — actividad distinta a la del servicio", "Excluido", "Anexo / exclusión", "Excluido", ""),
]
TAX: Dict[str, Subcomp] = {s.cod: s for s in TAXONOMIA}

# ── Clasificación real de Las Ceibas (saldos COP: 2024, 2025) ──
# Fuente: Maestro_Codificacion_Contable_CRA1032.xlsx, hoja Cruce_PlanCuentas
# (276 cuentas), reconciliada contra Resumen_Control. Procedencia: VALIDADA.
APERTURA_LASCEIBAS: Dict[str, Tuple[int, int]] = {
    "CAC-1": (15511705821, 15081519125),
    "CAC-1.COM": (0, 0),
    "CAC-2": (16833583485, 17311049061),
    "CAC-2.COM": (3189094366, 5086584244),
    "CAC-3": (91267062, 81506686),
    "CAC-4": (0, 0),
    "CAC-4.COM": (0, 0),
    "CAC-5": (0, 0),
    "CAC-6": (0, 0),
    "COC-1": (15558274487, 18548741927),
    "COC-2": (6536024763, 11174480601),
    "COC-3": (0, 0),
    "COC-4": (0, 0),
    "COC-5": (0, 0),
    "CE": (396736242, 412881183),       # energía CONTABLE (cuadre); reconocida aparte
    "CIQ": (0, 0),                       # químicos vienen del reporte CUP, no del balance
    "COIR": (1349166238, 3274205392),
    "CII": (10441199628, 6927592000),
    "CIAR": (0, 0),
    "CIAO": (930801186, 542808046),
    "ICTA": (3052522492, 1888930558),
    "ICTO": (2092533634, 1941897603),
    "TA": (2712336040, 705171886),
    "DEP": (11686551758, 13624608108),
    "CAC-X": (4012628572, 1954274487),
    "COC-X": (210250045, 255817421),
    "ICT-X": (4200674243, 6754482067),
    "NT": (-43537707553, -52132352688),
}

# Valores RECONOCIDOS que no salen del balance (año base 2024, pesos dic-2025),
# tomados del estudio verificado de Las Ceibas (caso de verificación del skill):
CE_RECONOCIDO_2024 = 389844472       # build de energía eficiente (art. 2.1.2.1.3.4.6)
CIQ_RECONOCIDO_2024 = 5931959600     # reporte CUP de químicos (art. 2.1.2.1.3.4.7)

# Totales de control esperados (Resumen_Control del Maestro), para la autoprueba:
CONTROL_2024 = {"CMA": 35625650734, "CMO": 23840201730, "CMI": 11372000814,
                "CMICT": 7857392166, "Excluido": -23427602935}

IDX = {2024: 0, 2025: 1}


def total_componente(apertura: Dict[str, Tuple[int, int]], comp: str, anio: int = 2024) -> int:
    i = IDX[anio]
    return sum(v[i] for c, v in apertura.items() if TAX[c].componente == comp)


def cace(apertura=APERTURA_LASCEIBAS, anio: int = 2024) -> int:
    """Numerador del CAC = suma de todos los CAC-* (incluye .COM); art. 2.1.2.1.3.2.4."""
    return total_componente(apertura, "CMA", anio)


def coce_comparables(apertura=APERTURA_LASCEIBAS, anio: int = 2024) -> int:
    """COCe = costos operativos comparables (COC-1..5); art. 2.1.2.1.3.4.4.
    NO incluye CE, CIQ ni COIR, que entran al COT como sumandos propios."""
    i = IDX[anio]
    return sum(apertura[c][i] for c in ("COC-1", "COC-2", "COC-3", "COC-4", "COC-5"))


def cat(apertura=APERTURA_LASCEIBAS, kct: float = 0.0154, anio: int = 2024) -> float:
    """CAT = CACe × (1+kct); numerador del CMA (art. 2.1.2.1.3.2.1)."""
    return cace(apertura, anio) * (1 + kct)


def cot(apertura=APERTURA_LASCEIBAS, kct: float = 0.0154, anio: int = 2024,
        ce_reconocido: float = None, ciq_reconocido: float = None) -> float:
    """COT = (COCe + CE + CIQ + COIR) × (1+kct); numerador del CMO (art. 2.1.2.1.3.4.1).
    Usa CE y CIQ RECONOCIDOS (no los contables) si se entregan."""
    i = IDX[anio]
    ce = ce_reconocido if ce_reconocido is not None else apertura["CE"][i]
    ciq = ciq_reconocido if ciq_reconocido is not None else apertura["CIQ"][i]
    coir = apertura["COIR"][i]
    return (coce_comparables(apertura, anio) + ce + ciq + coir) * (1 + kct)


def autoprueba():
    print("Reconciliación de la apertura contra el Resumen_Control (2024):")
    ok = True
    for comp, esperado in CONTROL_2024.items():
        got = total_componente(APERTURA_LASCEIBAS, comp, 2024)
        flag = "OK" if got == esperado else "DIFERENCIA"
        if got != esperado:
            ok = False
        print(f"  {comp:9} calculado {got:>18,.0f} | control {esperado:>18,.0f} | {flag}")
    print(f"\nCACe 2024            = {cace():>18,.0f}")
    print(f"COCe comparables 2024 = {coce_comparables():>18,.0f}")
    print(f"CAT = CACe×(1+kct)    = {cat():>18,.0f}  (kct=1,54%)")
    print(f"COT reconocido        = {cot(ce_reconocido=CE_RECONOCIDO_2024, ciq_reconocido=CIQ_RECONOCIDO_2024):>18,.0f}")
    print(f"  (con CE={CE_RECONOCIDO_2024:,} y CIQ={CIQ_RECONOCIDO_2024:,} reconocidos)")
    print("\nTODO RECONCILIA" if ok else "\n*** HAY DIFERENCIAS ***")
    return ok


# ── Reparto por servicio (Modelo completo V2: RESUMEN_COMP_SUBCOMP, 04a/04b, 05_CMO) ──
# Año base 2024 (i-2), saldos COP. Procedencia: VALIDADA. PEADMIN = PEOPER = 100% (inicio).
PERSERVICIO_2024 = {
    "CACe_maestro": {"ac": 20056103677, "al": 15569547057},      # subtotal CMA del Maestro
    "impacto_normativo_cma": {"ac": 104430574, "al": 75622140},  # impacto de normas (salario mínimo, etc.)
    "CACe": {"ac": 20160534251, "al": 15645169196},              # CAC post-impacto × PEADMIN
    "COCe": {"ac": 18627211481, "al": 3289403325},               # COC comparables post-impacto × PEOPER
    "CE": {"ac": 389844472, "al": 0},
    "CIQ": {"ac": 5931959600, "al": 0},
    "COIR": {"ac": 0, "al": 0},
    "N": {"ac": 132987.08, "al": 129075.58},
    "CCP": {"ac": 36831353, "al": 35720101},
    "Fa_cma": 1.06727106506171, "Fa_cmo": 1.06727106506171, "kct": 0.0154,
}
DRIVER_REPARTO = {
    "descripcion": "Los costos compartidos (códigos CO_*) se reparten entre servicios; "
                   "los directos se asignan en 04a/04b a nivel de cuenta.",
    "distribucion_global_ac": 0.8,
    "fuente": "hoja 'Reclasificación servicios' del Modelo completo",
}
CMA_OBJETIVO = {"ac": 13690.62, "al": 10946.29}   # $/susc·mes, dic-2025
CMO_OBJETIVO = {"ac": 734.09, "al": 99.80}        # $/m³, dic-2025


def cat_servicio(s):
    d = PERSERVICIO_2024
    return d["CACe"][s] * (1 + d["kct"])


def cot_servicio(s):
    d = PERSERVICIO_2024
    return (d["COCe"][s] + d["CE"][s] + d["CIQ"][s] + d["COIR"][s]) * (1 + d["kct"])


def cma_servicio(s):
    d = PERSERVICIO_2024
    return (cat_servicio(s) / (d["N"][s] * 12)) * d["Fa_cma"]


def cmo_servicio(s):
    d = PERSERVICIO_2024
    return (cot_servicio(s) / d["CCP"][s]) * d["Fa_cmo"]


def autoprueba_servicio():
    print("\nReparto por servicio (2024) y reconstrucción de CMA/CMO:")
    d = PERSERVICIO_2024
    ok = True
    for s, et in (("ac", "Acueducto"), ("al", "Alcantarillado")):
        cma, cmo = cma_servicio(s), cmo_servicio(s)
        oc, oo = CMA_OBJETIVO[s], CMO_OBJETIVO[s]
        fcma = "OK" if abs(cma - oc) / oc <= 0.005 else "DIF"
        fcmo = "OK" if abs(cmo - oo) / oo <= 0.005 else "DIF"
        if fcma != "OK" or fcmo != "OK":
            ok = False
        print(f"  {et:15} CAT {cat_servicio(s):>16,.0f} | CMA {cma:9,.2f} (obj {oc:9,.2f}) {fcma}")
        print(f"  {'':15} COT {cot_servicio(s):>16,.0f} | CMO {cmo:9,.2f} (obj {oo:9,.2f}) {fcmo}")
    tm = d["CACe_maestro"]["ac"] + d["CACe_maestro"]["al"]
    tp = d["CACe"]["ac"] + d["CACe"]["al"]
    print(f"  Cierre del 0,5%: CACe Maestro {tm:,.0f} + impacto normativo {tp - tm:,.0f} = CACe estudio {tp:,.0f}")
    print("  RECONSTRUYE CMA/CMO" if ok else "  *** DIFERENCIA ***")
    return ok


if __name__ == "__main__":
    autoprueba()
    autoprueba_servicio()
