-- =====================================================================
--  037_periodo_activo.sql — Año tarifario ACTIVO por empresa.
--  Gobierna la línea base que se carga y (en fases siguientes) qué secciones
--  del cargue aplican. Valores: 'inicio', 'a1' … 'a10' (clave de periodos.py).
--  Idempotente.
-- =====================================================================

ALTER TABLE empresa ADD COLUMN IF NOT EXISTS periodo_activo text NOT NULL DEFAULT 'inicio';
