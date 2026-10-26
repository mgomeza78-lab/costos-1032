-- =====================================================================
--  027_aps_balance.sql — Dimensión APS en los numeradores del balance.
--  Agrega `cod_dane` a numerador_mensual ('' = conjunto / todas las APS, lo
--  normal; un cod_dane = balance separado de ese APS). El total del mes es la
--  SUMA sobre cod_dane (así lo lee el recálculo). Idempotente; el DROP del
--  UNIQUE viejo se hace por su definición (no por el nombre autogenerado).
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

ALTER TABLE numerador_mensual ADD COLUMN IF NOT EXISTS cod_dane text NOT NULL DEFAULT '';

DO $$
DECLARE
  c record;
BEGIN
  FOR c IN
    SELECT conrelid::regclass::text AS tbl, conname
    FROM pg_constraint
    WHERE contype = 'u' AND conrelid = 'numerador_mensual'::regclass
      AND pg_get_constraintdef(oid) = 'UNIQUE (empresa_id, anio, mes, servicio, concepto)'
  LOOP
    EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tbl, c.conname);
  END LOOP;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'numerador_mensual_aps_key') THEN
    ALTER TABLE numerador_mensual ADD CONSTRAINT numerador_mensual_aps_key
      UNIQUE (empresa_id, anio, mes, servicio, concepto, cod_dane);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS numerador_mensual_aps_idx ON numerador_mensual (empresa_id, cod_dane, anio, mes);
