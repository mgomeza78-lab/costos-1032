-- =====================================================================
--  029_balance_cuentas.sql — Detalle por CUENTA del balance clasificado,
--  para el drill-down de cada subcomponente (CAC-1, CAC-2, …).
--  Guarda, por (empresa, año, cuenta), el subcomponente/componente y las
--  mismas cubetas que numerador_subcomp (ac_dir/al_dir = clase 7 directo;
--  repartir = clase 5 por %). Idempotente; rol dueño (postgres); RLS por empresa.
-- =====================================================================

CREATE TABLE IF NOT EXISTS numerador_cuenta (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  componente    text NOT NULL,
  subcomponente text NOT NULL,
  codigo        text NOT NULL,
  nombre        text,
  cod_dane      text NOT NULL DEFAULT '',
  ac_dir        double precision NOT NULL DEFAULT 0,
  al_dir        double precision NOT NULL DEFAULT 0,
  repartir      double precision NOT NULL DEFAULT 0,
  origen        text DEFAULT 'balance',
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, codigo, cod_dane)
);
CREATE INDEX IF NOT EXISTS numerador_cuenta_idx ON numerador_cuenta (empresa_id, anio, componente, subcomponente);

ALTER TABLE numerador_cuenta ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ncta_all ON numerador_cuenta;
CREATE POLICY ncta_all ON numerador_cuenta FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON numerador_cuenta TO app_user;
GRANT USAGE, SELECT ON SEQUENCE numerador_cuenta_id_seq TO app_user;
