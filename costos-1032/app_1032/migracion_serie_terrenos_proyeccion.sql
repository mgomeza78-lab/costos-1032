-- ============================================================================
-- Migración ADITIVA (2): componente terrenos en la serie + serie CCP proyectada 688
-- Correr UNA vez en Supabase (SQL Editor). Segura: solo AGREGA (IF NOT EXISTS).
-- ============================================================================

-- 1) Componente de terrenos en la serie del CMI688 (Paso 01).
--    En la 688 los terrenos solo se remuneraban (no se depreciaban); separarlo del
--    cmi_bcr permite un VP(CMI×Q) limpio por componente y la desagregación del ingreso.
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cmi_terrenos numeric;

-- 2) Serie CCP proyectada del 688 (el CCP con el que se fijaron las tarifas), por servicio y año.
--    Se compara contra el agua facturada real para explicar la BCR0 de entrada a la 1032.
CREATE TABLE IF NOT EXISTS bcr_proyeccion_688 (
  empresa_id        bigint  NOT NULL,
  servicio          text    NOT NULL,
  anio_tarifario    integer NOT NULL,
  ccp_proyectado    numeric,            -- m³/año proyectados (base del CMI 688)
  cmi688_proyectado numeric,            -- $/m³ (opcional, trazabilidad)
  PRIMARY KEY (empresa_id, servicio, anio_tarifario)
);
