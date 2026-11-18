-- ============================================================================
-- Migración ADITIVA (2): componente terrenos en la serie + serie CCP proyectada 688
-- Correr UNA vez en Supabase (SQL Editor) como rol 'postgres' (dueño).
-- Segura: solo AGREGA (IF NOT EXISTS) y fija permisos/RLS de la tabla nueva.
-- ============================================================================

-- 1) Componente de terrenos en la serie del CMI688 (Paso 01).
--    En la 688 los terrenos solo se remuneraban (no se depreciaban); separarlo del
--    cmi_bcr permite un VP(CMI×Q) limpio por componente y la desagregación del ingreso.
--    (Hereda permisos y RLS de bcr_serie; no requiere GRANT adicional.)
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS cmi_terrenos numeric;

-- 2) Serie CCP proyectada del 688 (el CCP con el que se fijaron las tarifas), por servicio y año.
--    Se compara contra el agua facturada real para explicar la BCR0 de entrada a la 1032.
CREATE TABLE IF NOT EXISTS bcr_proyeccion_688 (
  empresa_id        integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio          text    NOT NULL,
  anio_tarifario    integer NOT NULL,
  ccp_proyectado    numeric,            -- m³/año proyectados (base del CMI 688)
  cmi688_proyectado numeric,            -- $/m³ (opcional, trazabilidad)
  PRIMARY KEY (empresa_id, servicio, anio_tarifario)
);

-- 2b) RLS + permisos del rol de aplicación (igual que cmi_proyecto).
--     SIN esto, app_user NO puede leer ni escribir la tabla: el cargue y la consulta fallarían.
ALTER TABLE bcr_proyeccion_688 ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bcr_proy688_all ON bcr_proyeccion_688;
CREATE POLICY bcr_proy688_all ON bcr_proyeccion_688 FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON bcr_proyeccion_688 TO app_user;
