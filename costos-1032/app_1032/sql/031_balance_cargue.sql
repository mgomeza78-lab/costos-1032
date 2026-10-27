-- =====================================================================
--  031_balance_cargue.sql — Registro de CARGUES del balance de prueba.
--   Una fila por archivo cargado (empresa, año base, ámbito/APS): nombre
--   del archivo, rango de meses al que corresponde y TOTALES DE CONTROL
--   por clase PUC — clase 5 (gastos/administración) y clase 7 (costos/
--   operación) — sumando solo cuentas HOJA (sin doble conteo). Sirven para
--   reconciliar lo cargado contra el balance de la empresa, con trazabilidad
--   del archivo y del período. Reemplaza por (empresa, año, ámbito).
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

CREATE TABLE IF NOT EXISTS balance_cargue (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  cod_dane      text NOT NULL DEFAULT '',          -- '' = conjunto (toda la empresa)
  archivo       text NOT NULL DEFAULT '',
  mes_ini       smallint NOT NULL DEFAULT 1,
  mes_fin       smallint NOT NULL DEFAULT 12,
  total_clase5  double precision NOT NULL DEFAULT 0,
  total_clase7  double precision NOT NULL DEFAULT 0,
  n_cuentas     integer NOT NULL DEFAULT 0,
  n_sin         integer NOT NULL DEFAULT 0,
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, cod_dane)
);
CREATE INDEX IF NOT EXISTS balance_cargue_idx ON balance_cargue (empresa_id, anio);

ALTER TABLE balance_cargue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bcrg_all ON balance_cargue;
CREATE POLICY bcrg_all ON balance_cargue FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON balance_cargue TO app_user;
GRANT USAGE, SELECT ON SEQUENCE balance_cargue_id_seq TO app_user;
