-- =====================================================================
--  023_aprobacion_origen.sql — marca el origen de la aprobación.
--  'automatica' = borrador generado al procesar la actualización (con el
--  índice y la fecha usados); el usuario adjunta el acto administrativo.
--  'manual' = registrada a mano por el usuario.
-- =====================================================================
ALTER TABLE aprobacion_costos ADD COLUMN IF NOT EXISTS origen text NOT NULL DEFAULT 'manual';
