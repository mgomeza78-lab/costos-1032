-- =====================================================================
--  036_energia_mes.sql — Energía por MES.
--  Permite cargar el año completo (12 meses) o UN solo mes para corregirlo,
--  sin borrar el resto del año. La CE de cada punto es la suma de sus meses.
--    · mes = 0  → entrada ANUAL/consolidada (cargue anual o manual «año completo»).
--    · mes 1..12 → entrada mensual. Lo mensual sustituye a lo anual del mismo año.
--  Idempotente.
-- =====================================================================

ALTER TABLE energia_punto ADD COLUMN IF NOT EXISTS mes smallint NOT NULL DEFAULT 0;

-- El unicidad pasa a incluir el mes (una fila por punto y mes).
ALTER TABLE energia_punto DROP CONSTRAINT IF EXISTS energia_punto_empresa_id_anio_servicio_no_sui_punto_key;
CREATE UNIQUE INDEX IF NOT EXISTS energia_punto_uq
  ON energia_punto (empresa_id, anio, mes, servicio, no_sui, punto);
CREATE INDEX IF NOT EXISTS energia_punto_mes_idx
  ON energia_punto (empresa_id, anio, mes, servicio);
