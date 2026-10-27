-- =====================================================================
--  028_balance_subcomp.sql — Desglose del balance por SUBCOMPONENTE y año,
--  y parámetro de reparto por servicio de la clase 5 (CMA).
--
--  · numerador_subcomp: el balance de prueba clasificado, guardado por
--    (empresa, AÑO base, servicio, componente, subcomponente). Es la fuente de
--    la pantalla de balance (valor por período y acumulado, por componente).
--    El período de la línea base es el AÑO (art. de la línea base, Res. 1032);
--    por eso la granularidad es anual, no mensual.
--  · balance_reparto: el % de acueducto de la clase 5 (CMA y los impuestos
--    administrativos), editable por empresa (default 0.52, del modelo de Las
--    Ceibas). La clase 7 (CMO) se reparte por el servicio de cada cuenta.
--  Idempotente; se ejecuta como el rol dueño (postgres). RLS por empresa.
-- =====================================================================

-- Cubetas por (empresa, año, componente, subcomponente) para recomputar el reparto por servicio
-- con cualquier %: ac_dir/al_dir = contabilidad separada (clase 7); repartir = clase 5 (por %).
CREATE TABLE IF NOT EXISTS numerador_subcomp (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  componente    text NOT NULL,                 -- CMA | CMO | CMICT | CMI | Excluido
  subcomponente text NOT NULL,                 -- CAC-1, CAC-2, COC-1, CE, ICTA, ...
  cod_dane      text NOT NULL DEFAULT '',       -- '' = conjunto (lo normal)
  ac_dir        double precision NOT NULL DEFAULT 0,   -- clase 7 directo a acueducto
  al_dir        double precision NOT NULL DEFAULT 0,   -- clase 7 directo a alcantarillado
  repartir      double precision NOT NULL DEFAULT 0,   -- clase 5 a repartir por el %
  origen        text DEFAULT 'balance',
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, componente, subcomponente, cod_dane)
);
CREATE INDEX IF NOT EXISTS numerador_subcomp_idx ON numerador_subcomp (empresa_id, anio, componente);

CREATE TABLE IF NOT EXISTS balance_reparto (
  empresa_id integer PRIMARY KEY REFERENCES empresa(id) ON DELETE CASCADE,
  pct_ac     double precision NOT NULL DEFAULT 0.52,   -- participación de acueducto de la clase 5
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE numerador_subcomp ENABLE ROW LEVEL SECURITY;
ALTER TABLE balance_reparto   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS nsub_all ON numerador_subcomp;
CREATE POLICY nsub_all ON numerador_subcomp FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS brep_all ON balance_reparto;
CREATE POLICY brep_all ON balance_reparto FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON numerador_subcomp, balance_reparto TO app_user;
GRANT USAGE, SELECT ON SEQUENCE numerador_subcomp_id_seq TO app_user;
