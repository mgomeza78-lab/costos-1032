-- =====================================================================
--  022_aprobacion_indice.sql — anclar cada aprobación al índice usado.
--  La actualización se aprueba a precios del último índice publicado; el
--  monitoreo del 3% se mide frente a la FECHA de ese índice. Guardamos el
--  índice de referencia y su fecha en la aprobación.
-- =====================================================================
ALTER TABLE aprobacion_costos ADD COLUMN IF NOT EXISTS indice_referencia text;  -- p. ej. "IPCs dic-2026 = 112,34"
ALTER TABLE aprobacion_costos ADD COLUMN IF NOT EXISTS fecha_indice date;        -- fecha del índice usado (ancla del gatillo 3%)
