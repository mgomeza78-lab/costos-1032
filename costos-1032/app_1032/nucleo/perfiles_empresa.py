# -*- coding: utf-8 -*-
"""Registro de perfiles de empresa — capa común de la consolidación Res. CRA 1032.

Cada empresa se describe como un ``PerfilEmpresa``: identificación, segmento y
parámetros regulatorios, fechas y bases temporales, selectores metodológicos
adoptados, fuentes de datos por insumo y OBJETIVOS DE RECONCILIACIÓN —las cifras
ya aceptadas que cualquier corrida del marco unificado debe reproducir—.

Cada dato lleva su PROCEDENCIA, para no mezclar lo normativo, lo reportado/validado
por la empresa, lo radicado, lo trabajado ante la SSPD y lo que está por confirmar
(regla del proyecto: distinguir normativa / reportada / SUI / supuestos).

Fuentes primarias usadas aquí:
  · Res. CRA 1032 de 2026 y catálogo interno de variables/fórmulas (parámetros 2.º seg.).
  · Radicación ESSMAR (LÉAME de radicación y toolkit del modelo) — cifras de cierre.
  · Validación del motor de Neiva contra el modelo v69 (carpeta 07_Validacion).
  · Trabajo de amb ante la SSPD (docs del proyecto) — por confirmar contra el modelo.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List


class Proc(str, Enum):
    NORMATIVA = "normativa"          # del texto de la Res. 1032 / acto de la CRA
    VALIDADA = "validada"            # reportada por la empresa y ya reconciliada
    RADICADA = "radicada"            # cifra de un estudio ya radicado
    SSPD = "sspd"                    # de formatos/trabajo ante la SSPD
    POR_CONFIRMAR = "por_confirmar"  # aún no verificada contra fuente primaria


class Servicio(str, Enum):
    AC = "acueducto"
    AL = "alcantarillado"


@dataclass
class Dato:
    """Un valor con su procedencia y fuente (artículo o archivo)."""
    valor: object
    proc: Proc
    fuente: str = ""
    nota: str = ""


@dataclass
class Selector:
    """Un selector metodológico fijado en un criterio adoptado."""
    nombre: str
    valor_adoptado: str
    fundamento: str   # artículo de la Res. 1032


@dataclass
class Objetivo:
    """Cifra aceptada que el marco unificado debe reproducir (criterio de aceptación)."""
    servicio: Optional[Servicio]
    componente: str   # CMA, CMO, CMI, CMICT, CARGO_CONSUMO, FACTURA, FACTURA_CONJUNTA, BCR0, COC
    valor: float
    unidad: str
    proc: Proc
    fuente: str = ""
    tol_rel: float = 0.001   # tolerancia relativa por defecto: 0,1 %
    tol_abs: float = 0.0


@dataclass
class PerfilEmpresa:
    id: str
    nombre: str
    municipio: str
    segmento: int                       # 1 o 2 — art. 2.1.2.1.1.6
    servicios: List[Servicio]
    esquema: str                        # "por servicio" / "regional"
    parametros: Dict[str, Dato] = field(default_factory=dict)
    fechas: Dict[str, Dato] = field(default_factory=dict)
    selectores: List[Selector] = field(default_factory=list)
    fuentes_datos: Dict[str, str] = field(default_factory=dict)
    objetivos: List[Objetivo] = field(default_factory=list)
    rutas: Dict[str, str] = field(default_factory=dict)
    nuis: Optional[str] = None
    notas: str = ""
    numerador: Optional[Dict] = None   # apertura del numerador CAC/COC por subcomponente
    fecha_inicio_688: Optional[str] = None     # inicio real de aplicación de la Res. CRA 688 (varía por empresa)
    fecha_inicio_1032: Optional[str] = None    # inicio real de aplicación de la 1032 (puede ser posterior al período de inicio normativo)
    aplicacion_1032_tardia: bool = False       # True si la empresa aplica la 1032 después del 1-jul-2026


# ───────────────────────── Parámetros por segmento ─────────────────────────
# Art. 2.1.2.1.1.6: segmentación por suscriptores a 31-dic-2024.
#   2.º segmento: más de 90.000 y hasta 300.000 suscriptores.
#   1.er segmento: más de 300.000 suscriptores.
SEGMENTO_RANGO = {
    1: "más de 300.000 suscriptores (art. 2.1.2.1.1.6)",
    2: "más de 90.000 y hasta 300.000 suscriptores (art. 2.1.2.1.1.6)",
}


def params_segmento_2() -> Dict[str, Dato]:
    """Parámetros normativos del 2.º segmento confirmados para el período de inicio."""
    return {
        "r": Dato(0.0903, Proc.NORMATIVA, "art. 2.1.2.1.3.1.7"),
        "kct": Dato(0.0154, Proc.NORMATIVA, "art. 2.1.2.1.3.1.8",
                    "aplica sobre todo el componente (COT)"),
        "peadmin": Dato(1.0, Proc.NORMATIVA, "período de inicio"),
        "peoper": Dato(1.0, Proc.NORMATIVA, "período de inicio"),
        "ipuf_estrella_inicio": Dato(6.0, Proc.NORMATIVA, "art. 2.1.2.1.3.3.1 parág. 1",
                                     "6 m³/susc·mes para el 1-jul-2026, todo segmento"),
        "estandar_ipuf": Dato(4.0, Proc.NORMATIVA, "art. 2.1.2.1.2.2",
                              "estándar final del indicador de pérdidas, 2.º seg."),
        "gradualidad_ipuf": Dato([6, 6, 6, 5, 5, 4], Proc.NORMATIVA, "art. 2.1.2.1.2.3",
                                 "senda de gradualidad del IPUF* por año tarifario, 2.º seg."),
        "AT": Dato(0.5, Proc.NORMATIVA, "CMI año 1"),
        "per": Dato(2, Proc.NORMATIVA, "CMI año 1"),
        "cmi_poir": Dato(0.0, Proc.NORMATIVA, "CMI_POIR = 0 hasta 2027"),
    }


def params_segmento_1() -> Dict[str, Dato]:
    """Parámetros del 1.er segmento. r y kct POR CONFIRMAR contra el acto de la CRA/modelo."""
    return {
        "r": Dato(0.0858, Proc.POR_CONFIRMAR, "1.er segmento",
                  "registrado del trabajo de amb; confirmar contra fuente primaria"),
        "kct": Dato(0.0178, Proc.POR_CONFIRMAR, "1.er segmento",
                    "registrado del trabajo de amb; confirmar"),
        "peadmin": Dato(1.0, Proc.NORMATIVA, "período de inicio"),
        "peoper": Dato(1.0, Proc.NORMATIVA, "período de inicio"),
        "ipuf_estrella_inicio": Dato(6.0, Proc.NORMATIVA, "art. 2.1.2.1.3.3.1 parág. 1"),
        "estandar_ipuf": Dato(None, Proc.POR_CONFIRMAR, "art. 2.1.2.1.2.2",
                              "estándar y gradualidad del 1.er seg. por confirmar"),
    }


def fechas_periodo_inicio() -> Dict[str, Dato]:
    """Fechas y bases temporales comunes del período de inicio (todas las empresas)."""
    return {
        "inicio_periodo": Dato("2026-07-01", Proc.NORMATIVA, "art. 2.1.2.1.1.8"),
        "fin_periodo": Dato("2026-12-31", Proc.NORMATIVA, "art. 2.1.2.1.1.8 parág. 1"),
        "primer_anio_tarifario": Dato("2027-01-01 a 2027-12-31", Proc.NORMATIVA,
                                      "año tarifario 1 (distinto del período de inicio)"),
        "base_pesos": Dato("dic-2025", Proc.NORMATIVA, "base de indexación"),
        "anio_base_cma_cmo": Dato(2024, Proc.NORMATIVA, "i-2"),
        "anio_base_cmict": Dato(2025, Proc.NORMATIVA, "i-1"),
        "corte_bcr0": Dato("2026-06-30", Proc.NORMATIVA, "BCR0 al 30-jun-2026"),
    }


# ───────────────────────────── ESSMAR (Santa Marta) ─────────────────────────────
def _essmar() -> PerfilEmpresa:
    p = PerfilEmpresa(
        id="ESSMAR",
        nombre="ESSMAR E.S.P.",
        municipio="Santa Marta (Magdalena)",
        segmento=2,
        servicios=[Servicio.AC, Servicio.AL],
        esquema="por servicio",
        parametros=params_segmento_2(),
        fechas=fechas_periodo_inicio(),
        selectores=[
            Selector("Valoración de la base de capital heredada",
                     "31 de mayo de 2019 — valor y fecha de referencia",
                     "art. 2.1.2.1.3.5.5"),
            Selector("CMI cobrado entre may-2019 y may-2021",
                     "Con compensación (valor pendiente negativo que se descuenta)",
                     "art. 2.1.2.1.5.2.1.1 (con numeral iii del art. 2.1.2.1.3.5.5)"),
            Selector("Descuento del recaudo del CMI 688",
                     "Mes a mes, exponente k/12",
                     "art. 2.1.2.1.3.5.5"),
        ],
        fuentes_datos={
            "suscriptores": "propio (facturación ESSMAR)",
            "consumos": "propio (facturación ESSMAR)",
            "estados_financieros": "propio (EEFF NIIF 2024/2025)",
            "activos_bcr0": "propio (Acuerdo 007 de 2021 / inventario)",
            "tasas_ambientales": "propio (facturas CORPAMAG)",
        },
        rutas={
            "estudio": r"Consultoría\Santa Marta\...\1. Radicacion CRA\ESSMAR - Estudio de costos Res CRA 1032.docx",
            "modelo_radicado": r"...\1. Radicacion CRA\ESSMAR - Modelo Res CRA 1032.xlsx",
            "modelo_completo": r"...\2. Documentos internos\ESSMAR - Modelo Res CRA 1032 (completo).xlsx",
        },
        notas="Estudio RADICADO ante la CRA. Verdad de cálculo = workbook de Excel "
              "(24/26 hojas, 34.461 fórmulas). BCR0 escenario radicado: AC $339.104 M, AL $330.604 M.",
    )
    p.parametros["consumo_propio_2025_ac"] = Dato(9.4605, Proc.RADICADA, "facturación ESSMAR 2025", "m³/susc·mes")
    p.parametros["consumo_propio_2025_al"] = Dato(8.9074, Proc.RADICADA, "facturación ESSMAR 2025", "m³/susc·mes")
    p.parametros["r_heredada_688"] = Dato(None, Proc.POR_CONFIRMAR, "Res. CRA 688/2014",
                                          "r688 usado en el descuento del recaudo; leer del modelo")
    f = "Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025"
    fc = "núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0"
    cmi_fac = "núcleo bcr0_cmi vs 17_BCR0 (CMI_BCR dic-2025); radicado indexado ×faep0"
    p.objetivos = [
        Objetivo(Servicio.AC, "CMA", 7695.77, "$/susc·mes", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMO", 1061.90, "$/m³", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMI", 1584.71, "$/m³", Proc.VALIDADA, cmi_fac, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMICT", 94.39, "$/m³", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AL, "CMA", 5104.13, "$/susc·mes", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AL, "CMO", 674.62, "$/m³", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AL, "CMI", 1904.48, "$/m³", Proc.VALIDADA, cmi_fac, tol_rel=0.002),
        Objetivo(Servicio.AL, "CMICT", 438.75, "$/m³", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AC, "FACTURA", 35098.66, "$/mes", Proc.RADICADA, f + " (indexado ×faep0)"),
        Objetivo(Servicio.AL, "FACTURA", 33404.17, "$/mes", Proc.RADICADA, f + " (indexado ×faep0)"),
        Objetivo(None, "FACTURA_CONJUNTA", 68502.83, "$/mes", Proc.RADICADA, f + " (indexado ×faep0)"),
        Objetivo(Servicio.AC, "BCR0", 339104e6, "$", Proc.RADICADA, f, tol_rel=0.002),
        Objetivo(Servicio.AL, "BCR0", 330604e6, "$", Proc.RADICADA, f, tol_rel=0.002),
    ]
    # Particularidad ESSMAR: aplicó la 688 desde mayo de 2019 (t = 7,0833 años,
    # descuento del recaudo mes a mes) y aplicará la 1032 TARDE (posterior al
    # 1-jul-2026), lo que la norma no contempla pero es una realidad.
    p.numerador = {"cmi_bcr0_2024": {
        "BCR0": {"ac": 339104476405, "al": 330604097769},
        "CMI_BCR_dic2025": {"ac": 1584.71, "al": 1904.48},
        "CMI_radicado_indexado": {"ac": 1660.27, "al": 1995.28},
        "CCP_i1": {"ac": 28736405.80, "al": 26668055.05},
        "compensacion": {"ac": -97085365118, "al": -20556976862},
        "fuente": "Modelo completo 17_BCR0/18_CMI; núcleo bcr0_cmi reconstruye BCR0 y CMI_BCR al peso",
        "nota": "Cargos radicados (CMA/CMO/CMI/CMICT) INDEXADOS ×faep0; el núcleo produce la base dic-2025.",
    }}
    p.fecha_inicio_688 = "2019-05-31"
    p.fecha_inicio_1032 = None          # por confirmar: posterior al 1-jul-2026
    p.aplicacion_1032_tardia = True
    return p


# ───────────────────────────── Las Ceibas (Neiva) ─────────────────────────────
def _neiva() -> PerfilEmpresa:
    p = PerfilEmpresa(
        id="LAS_CEIBAS",
        nombre="Las Ceibas E.P. de Neiva E.S.P.",
        municipio="Neiva (Huila)",
        segmento=2,
        servicios=[Servicio.AC, Servicio.AL],
        esquema="por servicio",
        parametros=params_segmento_2(),
        fechas=fechas_periodo_inicio(),
        selectores=[
            Selector("Valoración de la base de capital heredada",
                     "por definir en el recálculo del CMI independiente (06_BCR0)",
                     "art. 2.1.2.1.3.5.5"),
        ],
        fuentes_datos={
            "suscriptores": "SUI (form. 6080) / propio",
            "consumos": "SUI (form. 6080 / acu_com_096-097) / propio",
            "estados_financieros": "propio (EEFF NIIF 2024/2025)",
            "perdidas": "SUI (form. 6084 / SURICATA)",
            "activos_bcr0": "propio (inventario) / SUI 6089-6090",
        },
        rutas={"modelo": r"SICTAAA\Modelo_2APS_LasCeibas_CRA1032_2026_69.xlsx",
               "estudio": r"SICTAAA\Software...\08_Estudio_real_Neiva\Documento_soporte_Neiva_REAL_2026.docx"},
        notas="Motor Python validado vs modelo v69. Pendiente: recálculo CMI independiente "
              "desde inventario 06_BCR0; constancia ISUF; indexación faep0 al 1-jul-2026.",
    )
    p.parametros["r_heredada_825"] = Dato(0.1485, Proc.VALIDADA, "catálogo interno",
                                          "r825 para reconstruir BCR0; r688 por confirmar")
    f = "motor_1032 reconciliado vs modelo v69 (07_Validacion)"
    p.objetivos = [
        Objetivo(Servicio.AC, "CMO", 734.09, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AC, "CMI", 832.06, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AC, "CMICT", 103.92, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AL, "CMO", 99.80, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AL, "CMI", 1267.04, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AL, "CMICT", 192.90, "$/m³", Proc.VALIDADA, f, tol_rel=0.005),
        Objetivo(Servicio.AC, "CMA", 13690.62, "$/susc·mes", Proc.VALIDADA, "núcleo numerador por servicio", tol_rel=0.005),
        Objetivo(Servicio.AL, "CMA", 10946.29, "$/susc·mes", Proc.VALIDADA, "núcleo numerador por servicio", tol_rel=0.005),
        Objetivo(Servicio.AC, "BCR0", 207518425294.0, "$", Proc.VALIDADA, "núcleo bcr0_cmi vs modelo 06_BCR0", tol_rel=0.001),
        Objetivo(Servicio.AL, "BCR0", 291752478328.0, "$", Proc.VALIDADA, "núcleo bcr0_cmi vs modelo 06_BCR0", tol_rel=0.001),
    ]
    p.numerador = {
        "fuente": "Maestro_Codificacion_Contable_CRA1032.xlsx (Cruce_PlanCuentas, 276 cuentas), reconciliado Resumen_Control",
        "proc": Proc.VALIDADA.value,
        "anio_base_cma_cmo": 2024,
        "CACe_total": 35625650734,             # Sigma CAC-* (incluye traslado comercial .COM)
        "traslado_comercial_COM": 3189094366,  # clase 7 -> CMA (lectura/facturacion)
        "COCe_comparables": 22094299250,        # COC-1 + COC-2
        "CE_contable": 396736242,               # energia del balance (solo cuadre)
        "CE_reconocido": 389844472,             # build eficiente (art. 2.1.2.1.3.4.6)
        "CIQ_reconocido": 5931959600,           # reporte CUP (art. 2.1.2.1.3.4.7); CIQ contable = 0
        "COIR": 1349166238,
        "por_servicio_2024": {
            "CACe": {"ac": 20160534251, "al": 15645169196},
            "COCe": {"ac": 18627211481, "al": 3289403325},
            "CMA": {"ac": 13690.62, "al": 10946.29},
            "CMO": {"ac": 734.09, "al": 99.80},
            "impacto_normativo": {"ac": 104430574, "al": 75622140},
        },
        "driver_reparto": "hoja 'Reclasificación servicios' del Modelo completo (distribución global 0,8 ac); directos por cuenta en 04a/04b",
        "nota_servicio": "Reparto AC/AL incorporado (Modelo completo V2); reconstruye CMA 13.690,62/10.946,29 y CMO 734,09/99,80. El 0,5% vs el Maestro es el impacto de modificaciones normativas.",
        "cmi_bcr0_2024": {
            "BCR0": {"ac": 207518425294, "al": 291752478328},
            "CMI": {"ac": 832.06, "al": 1267.04},
            "compensacion_negativos": {"ac": -43861753679, "al": -61451963943},
            "n_activos": {"ac": 558, "al": 594},
            "fuente": "Modelo 06_BCR0 (1152 activos); núcleo bcr0_cmi.py reconstruye el CMI al peso",
        },
        "modulo": "09_Consolidacion_multiempresa/numerador_cac_coc.py",
    }
    p.fecha_inicio_688 = None           # por confirmar; el modelo 06_BCR0 usa t = 10 años
    p.fecha_inicio_1032 = "2026-07-01"  # período de inicio normativo
    return p


# ───────────────────────────── amb (Bucaramanga) ─────────────────────────────
def _amb() -> PerfilEmpresa:
    p = PerfilEmpresa(
        id="AMB",
        nombre="Acueducto Metropolitano de Bucaramanga S.A. E.S.P.",
        municipio="Área Metropolitana de Bucaramanga (Santander)",
        segmento=1,
        servicios=[Servicio.AC],  # AL por confirmar
        esquema="por confirmar (posible esquema regional metropolitano)",
        parametros=params_segmento_1(),
        fechas=fechas_periodo_inicio(),
        selectores=[],  # por leer del modelo cuando se conecte la carpeta
        fuentes_datos={"activos_bcr0": "propio (formato BCR0 SSPD)",
                       "costos": "propio (modelo amb)"},
        rutas={"carpeta": r"Consultoría\Bucaramanga\Estudio de costos 1032\Version Final",
               "formato_bcr0": r"...\Formato BCR\Formato_BCR0_amb_diligenciado_6.xlsx"},
        notas="Trabajo ante la SSPD: BCR0 diligenciado (2.666 activos), COC reconstruido, auditoría, "
              "sustentación. Solo acueducto (alcantarillado vía peaje a EMPAS). Núcleo valida BCR0 y CMI al peso.",
    )
    p.parametros["r"] = Dato(0.0858, Proc.VALIDADA, "art. 2.1.2.1.3.1.7 / formato BCR0 campo 37",
                             "1.er segmento, confirmado (V-24)")
    p.parametros["kct"] = Dato(0.0178, Proc.VALIDADA, "art. 2.1.2.1.3.1.8 / modelo amb", "1,78%")
    p.parametros["r_heredada_688"] = Dato(0.1228, Proc.VALIDADA, "Res. CRA 688/2014 art. 46",
                                          "verificado en el formato BCR0 (V-03)")
    p.parametros["CCP_i1_ac"] = Dato(53545843, Proc.VALIDADA, "modelo amb (volúmenes)", "m³/año")
    f = "núcleo bcr0_cmi vs Formato_BCR0_amb_diligenciado (2.666 activos); reproduce al peso"
    fc = "núcleo componentes vs modelo amb VF (dic-2025)"
    p.objetivos = [
        Objetivo(Servicio.AC, "CMA", 9016.64, "$/susc·mes", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMO", 2336.47, "$/m³", Proc.VALIDADA, fc, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMI", 2297.37, "$/m³", Proc.VALIDADA, f, tol_rel=0.002),
        Objetivo(Servicio.AC, "CMICT", 101.68, "$/m³", Proc.VALIDADA,
                 "núcleo (reproduce el modelo); incluye doble conteo del impuesto de vehículos $7,2M — limpio 101,54 (hallazgo CMICT!D33)", tol_rel=0.002),
        Objetivo(Servicio.AC, "BCR0", 1080558309074.0, "$", Proc.VALIDADA, f, tol_rel=0.001),
        Objetivo(None, "COC", 85094645944.0, "$", Proc.VALIDADA, "COCe del CMO (hoja 05a); reproducido dentro del CMO 2.336,47"),
    ]
    p.numerador = {"cmi_bcr0_2024": {
        "BCR0": {"ac": 1080558309074}, "CI": {"ac": 123014612759},
        "cak": {"ac": 30302709840}, "CMI": {"ac": 2297.37},
        "CCP_i1": {"ac": 53545843}, "compensacion": {"ac": -44424749243},
        "n_activos": {"ac": 2666},
        "fuente": "Formato_BCR0_amb_diligenciado_6.xlsx (FORMATO); núcleo bcr0_cmi reproduce BCR0 y CMI al peso",
        "nota": "Solo acueducto (alcantarillado vía peaje a EMPAS). 1.er segmento, r=8,58%.",
    }}
    p.fecha_inicio_688 = "2016-07-01"   # 688 desde jul-2016, t = 10 años
    p.fecha_inicio_1032 = "2026-07-01"  # aplicación en el período de inicio (a tiempo)
    return p


def cargar_perfiles() -> List[PerfilEmpresa]:
    return [_neiva(), _essmar(), _amb()]


PERFILES = {p.id: p for p in cargar_perfiles()}


if __name__ == "__main__":
    for p in cargar_perfiles():
        print(f"{p.id:12} seg {p.segmento}  {p.nombre}  — {len(p.objetivos)} objetivos, "
              f"{len(p.selectores)} selectores")
