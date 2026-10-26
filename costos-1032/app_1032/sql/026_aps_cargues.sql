-- =====================================================================
--  026_aps_cargues.sql — Dimensión APS en los cargues mensuales.
--  Agrega la columna `cod_dane` (código DANE del municipio = llave del APS,
--  art. 2.1.2.1.1.5) a las tablas de cargue que pueden desagregarse por APS.
--  '' (cadena vacía) = CONJUNTO / todas las APS (comportamiento actual).
--  Un cod_dane no vacío = el dato pertenece al APS de ese municipio.
--  Se usa '' en vez de NULL para que el UNIQUE/ON CONFLICT del upsert funcione
--  (en Postgres cada NULL es distinto en un índice único).
--  Se ejecuta como el rol dueño (postgres). Idempotente.
-- =====================================================================

-- ---------- Agua producida / macromedición (se carga POR APS) ----------
ALTER TABLE macromedicion         ADD COLUMN IF NOT EXISTS cod_dane text NOT NULL DEFAULT '';
-- ---------- Comercial: resumen y detalle por clase (desagregan por APS) ----------
ALTER TABLE carga_mensual         ADD COLUMN IF NOT EXISTS cod_dane text NOT NULL DEFAULT '';
ALTER TABLE carga_mensual_detalle ADD COLUMN IF NOT EXISTS cod_dane text NOT NULL DEFAULT '';

-- Reemplaza los UNIQUE para incluir cod_dane (mismo registro por APS y por conjunto).
-- Se elimina el UNIQUE antiguo buscándolo por su DEFINICIÓN (no por su nombre autogenerado),
-- para que la migración funcione igual en local y en Supabase aunque el nombre difiera.
DO $$
DECLARE
  c record;
BEGIN
  FOR c IN
    SELECT conrelid::regclass::text AS tbl, conname
    FROM pg_constraint
    WHERE contype = 'u' AND (
      (conrelid = 'macromedicion'::regclass
         AND pg_get_constraintdef(oid) = 'UNIQUE (empresa_id, anio, mes, servicio, punto)')
      OR (conrelid = 'carga_mensual'::regclass
         AND pg_get_constraintdef(oid) = 'UNIQUE (empresa_id, anio, mes, servicio)')
      OR (conrelid = 'carga_mensual_detalle'::regclass
         AND pg_get_constraintdef(oid) = 'UNIQUE (empresa_id, anio, mes, servicio, clase)')
    )
  LOOP
    EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tbl, c.conname);
  END LOOP;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'macromedicion_aps_key') THEN
    ALTER TABLE macromedicion ADD CONSTRAINT macromedicion_aps_key
      UNIQUE (empresa_id, anio, mes, servicio, punto, cod_dane);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'carga_mensual_aps_key') THEN
    ALTER TABLE carga_mensual ADD CONSTRAINT carga_mensual_aps_key
      UNIQUE (empresa_id, anio, mes, servicio, cod_dane);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'carga_mensual_detalle_aps_key') THEN
    ALTER TABLE carga_mensual_detalle ADD CONSTRAINT carga_mensual_detalle_aps_key
      UNIQUE (empresa_id, anio, mes, servicio, clase, cod_dane);
  END IF;
END $$;

-- Índices para filtrar/ordenar por APS en la vista "Cargado".
CREATE INDEX IF NOT EXISTS macromedicion_aps_idx         ON macromedicion         (empresa_id, cod_dane, anio, mes);
CREATE INDEX IF NOT EXISTS carga_mensual_aps_idx         ON carga_mensual         (empresa_id, cod_dane, anio, mes);
CREATE INDEX IF NOT EXISTS carga_mensual_detalle_aps_idx ON carga_mensual_detalle (empresa_id, cod_dane, anio, mes);
