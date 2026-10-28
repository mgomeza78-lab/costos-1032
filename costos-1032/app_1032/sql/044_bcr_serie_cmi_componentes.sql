-- =====================================================================
--  044_bcr_serie_cmi_componentes.sql — CMI688 cargado por COMPONENTE.
--
--  El CMI688 de la serie de agua facturada se descompone en sus dos componentes,
--  ambos en precios constantes de DICIEMBRE DE 2014 (base de la 688):
--    · `cmi_poir` = componente del Plan de Obras e Inversiones Reguladas (POIR 688).
--        Fuente del modelo: hoja «06_3_VI688 (POIR)», columnas mensuales P+ (está por
--        activo; se carga la SUMA de todos los activos del servicio).
--    · `cmi_bcr`  = componente de la Base de Capital Regulada inicial (BCR₀ 688).
--        Fuente del modelo: hoja «06_5_VI_688 BCR0», filas 162 (acueducto) y 163
--        (alcantarillado), columnas mensuales K+ (ya sumado por servicio).
--  El CMI688 total que entra al VP(CMI×Q) del VPR₀ es la SUMA de ambos:
--        CMI688 = cmi_poir + cmi_bcr   (art. 2.1.2.1.3.5.5).
--  `cmi_cobrado` (migración 043) permanece como total dic-2014 para compatibilidad:
--  el cálculo usa cmi_poir+cmi_bcr cuando existen, y cae a cmi_cobrado si no.
--  Idempotente.
-- =====================================================================

ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cmi_poir double precision;  -- componente POIR 688 (dic-2014)
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cmi_bcr  double precision;  -- componente BCR₀ 688 (dic-2014)

COMMENT ON COLUMN bcr_serie.cmi_poir IS 'CMI688 componente POIR, precios dic-2014 (06_3 Σactivos por servicio)';
COMMENT ON COLUMN bcr_serie.cmi_bcr  IS 'CMI688 componente BCR₀, precios dic-2014 (06_5 filas 162/163 por servicio)';
