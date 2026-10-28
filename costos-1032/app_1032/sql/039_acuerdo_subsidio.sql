-- =====================================================================
--  039_acuerdo_subsidio.sql — Acuerdo del Concejo Municipal de subsidios y contribuciones.
--
--  Los porcentajes (factores) de subsidio y contribución NO se derivan del formato
--  comercial: los fija el Concejo Municipal por anualidad mediante acuerdo (Ley 142 de
--  1994, art. 89.1; límites de la Ley 1450 de 2011, art. 125; Decreto 1077 de 2015,
--  art. 2.3.4.2.x). Esta tabla registra, por VIGENCIA (año), el acuerdo del concejo que
--  soporta los factores cargados en `factor_subsidio` para ese año, incluido el documento
--  escaneado del acuerdo. Los factores por clase siguen en `factor_subsidio` (005).
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

CREATE TABLE IF NOT EXISTS acuerdo_subsidio (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  vigencia       smallint NOT NULL,                 -- año de aplicación del acuerdo
  numero_acuerdo text,                              -- n.º del acuerdo del concejo
  fecha_acuerdo  date,                              -- fecha de expedición
  concejo        text,                              -- concejo/municipio que lo expide
  observacion    text,
  soporte_nombre text,                              -- documento del acuerdo (opcional)
  soporte_tipo   text,
  soporte_tam    integer,
  soporte        bytea,
  cargado_por    integer REFERENCES usuario(id),
  cargado_en     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, vigencia)
);
CREATE INDEX IF NOT EXISTS acuerdo_subsidio_idx ON acuerdo_subsidio (empresa_id, vigencia);

ALTER TABLE acuerdo_subsidio ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS acsub_all ON acuerdo_subsidio;
CREATE POLICY acsub_all ON acuerdo_subsidio FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON acuerdo_subsidio TO app_user;
GRANT USAGE, SELECT ON SEQUENCE acuerdo_subsidio_id_seq TO app_user;
