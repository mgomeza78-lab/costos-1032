-- ============================================================================
-- Migración ADITIVA: metadata de trazabilidad de la valoración en cmi_proyecto
-- Correr UNA vez en Supabase (SQL Editor) ANTES de recargar el BCR.
-- Es segura: solo AGREGA columnas (IF NOT EXISTS), no modifica ni borra datos.
-- ============================================================================
ALTER TABLE cmi_proyecto
  ADD COLUMN IF NOT EXISTS origen          text,     -- VI287 / VIdif287
  ADD COLUMN IF NOT EXISTS subsistema      text,     -- p.ej. Producción de agua potable
  ADD COLUMN IF NOT EXISTS actividad       text,     -- p.ej. Captación, Tratamiento
  ADD COLUMN IF NOT EXISTS tipo_activo     text,     -- p.ej. Plantas, Terrenos, Tubería
  ADD COLUMN IF NOT EXISTS fecha_operacion date,     -- fecha de entrada en operación
  ADD COLUMN IF NOT EXISTS valor_total     numeric,  -- valor total del activo (dic-2014)
  ADD COLUMN IF NOT EXISTS to_anios        numeric,  -- tiempo de operación (años) a 2026-06-30
  ADD COLUMN IF NOT EXISTS vur_anios       numeric,  -- vida útil remanente (al inicio 688)
  ADD COLUMN IF NOT EXISTS observacion     text;     -- notas (terrenos, fechas estimadas, etc.)
