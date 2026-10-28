-- =====================================================================
--  043_bcr_serie_aps_cmi.sql — Serie de agua facturada 688 por APS y CMI en dos bases.
--
--  (1) Se carga SEPARADA POR APS (las áreas de prestación configuradas de la empresa):
--      se agrega la dimensión `cod_dane` a la serie y a su llave primaria.
--  (2) El CMI688 cobrado se registra en DOS bases de precios:
--      · `cmi_cobrado`  = CMI en precios constantes de DICIEMBRE DE 2014 (OBLIGATORIO; es el
--        que entra al VP(CMI×Q) del VPR₀, consistente con el VIA688 en $dic-2014).
--      · `cmi_corriente` = CMI en precios corrientes del año (opcional, trazabilidad).
--  (3) El `segmento` por fila queda OBSOLETO (el segmento 688 se deriva del nivel de empresa,
--      por los suscriptores): la columna permanece pero ya no se carga ni se exige.
--  Idempotente.
-- =====================================================================

ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cod_dane text NOT NULL DEFAULT '';   -- APS (DIVIPOLA); '' = conjunto
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cmi_corriente double precision;      -- CMI en precios corrientes

-- Llave primaria por APS (antes: empresa, servicio, anio_tarifario, mes).
ALTER TABLE bcr_serie DROP CONSTRAINT IF EXISTS bcr_serie_pkey;
ALTER TABLE bcr_serie ADD CONSTRAINT bcr_serie_pkey
  PRIMARY KEY (empresa_id, servicio, cod_dane, anio_tarifario, mes);

COMMENT ON COLUMN bcr_serie.cmi_cobrado  IS 'CMI688 cobrado en precios constantes dic-2014 (obligatorio; VP(CMI×Q))';
COMMENT ON COLUMN bcr_serie.cmi_corriente IS 'CMI688 cobrado en precios corrientes (opcional, trazabilidad)';
COMMENT ON COLUMN bcr_serie.cod_dane     IS 'APS (código DIVIPOLA) a la que corresponde la serie';
