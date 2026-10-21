-- =====================================================================
--  009_subsidios_supabase.sql — DELTA para una base que ya tiene cargadas
--  las migraciones 001 a 008 (como tu proyecto de Supabase actual).
--
--  Agrega la dimensión OPCIONAL de APS/municipio a la tabla del comercial,
--  para poder separar el balance de subsidios y contribuciones por área de
--  prestación (el Fondo de Solidaridad es municipal). No borra ni cambia
--  ningún dato existente.
--
--  Cómo correrlo: Supabase → SQL Editor → pega todo esto → RUN.
-- =====================================================================

ALTER TABLE carga_mensual_detalle ADD COLUMN IF NOT EXISTS municipio text;
CREATE INDEX IF NOT EXISTS ix_cmd_mpio ON carga_mensual_detalle(empresa_id, municipio);
