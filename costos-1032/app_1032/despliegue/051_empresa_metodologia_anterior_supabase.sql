-- 051_empresa_metodologia_anterior_supabase.sql — Metodología tarifaria anterior del prestador. Ejecutar en Supabase (editor SQL). Idéntico a sql/051_empresa_metodologia_anterior.sql.

-- =====================================================================
--  051_empresa_metodologia_anterior.sql — Metodología tarifaria anterior del prestador.
--
--  Al crear/editar la empresa se elige explícitamente qué metodología venía aplicando
--  (Res. CRA 688 de 2014 o Res. CRA 825 de 2017). Antes se infería de la fecha de inicio
--  de la 688; ahora es un dato declarado del prestador y el sistema lo usa de ahí en
--  adelante (p. ej. para el Fap del CCP: columna 688/825 de la tabla del parágrafo 3).
--  Rol dueño (postgres). Idempotente.
-- =====================================================================

ALTER TABLE empresa ADD COLUMN IF NOT EXISTS metodologia_anterior text;  -- '688' | '825' | NULL

-- Siembra: las empresas que ya tienen registrada una fecha de inicio de la 688 venían
-- aplicando la 688 (las que aplicaron la 825 no tienen esa fecha).
UPDATE empresa SET metodologia_anterior = '688'
 WHERE metodologia_anterior IS NULL AND fecha_inicio_688 IS NOT NULL;

-- Restricción de dominio (idempotente: se recrea).
ALTER TABLE empresa DROP CONSTRAINT IF EXISTS empresa_metodologia_anterior_chk;
ALTER TABLE empresa ADD  CONSTRAINT empresa_metodologia_anterior_chk
  CHECK (metodologia_anterior IS NULL OR metodologia_anterior IN ('688', '825'));

COMMENT ON COLUMN empresa.metodologia_anterior IS
  'Metodología tarifaria que venía aplicando el prestador (688|825), elegida en crear/editar empresa. '
  'Fuente explícita de la metodología anterior para el Fap del CCP y la transición; si es NULL se infiere de fecha_inicio_688.';
