-- =====================================================================
--  035_cmict_tasas.sql — Módulo CMICT al detalle (art. 2.1.2.1.3.6).
--    · cmict_tributo     : ICTA (15 conceptos, .6.3) e ICTO (8 conceptos, .6.4) al
--        detalle, con bandera «incluye» (SI/NO SE INCLUYE) y el valor efectivamente
--        pagado por concepto y servicio. El total del balance se muestra como
--        referencia contable; esto lo refina al efectivamente pagado y reconocible.
--    · tasa_tua          : Tasa por Uso del Agua (acueducto, .6.5). Una fila por
--        factura/concesión; valor efectivamente pagado (par. 4).
--    · tasa_retributiva  : Tasa retributiva por vertimientos (alcantarillado, .6.6).
--        Una fila por punto de vertimiento; se reconoce a Frec = 1 (el mayor valor
--        por FR>1 por incumplimiento de metas NO es trasladable).
--    · tasa_soporte      : soportes (facturas/comprobantes de pago) en PDF/imagen,
--        ligados a una tasa (como aps_archivo).
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

CREATE TABLE IF NOT EXISTS cmict_tributo (
  id           serial PRIMARY KEY,
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio         smallint NOT NULL,
  servicio     text NOT NULL,                     -- acueducto | alcantarillado
  componente   text NOT NULL,                     -- ICTA | ICTO
  item         text NOT NULL,                     -- llave 3.a-1..3.a-15 / 4.a-1..4.a-8
  incluye      boolean NOT NULL DEFAULT true,     -- SI SE INCLUYE / NO SE INCLUYE
  valor_pagado double precision,                  -- efectivamente pagado 2025 ($)
  observacion  text,
  origen       text NOT NULL DEFAULT 'empresa',
  cargado_por  integer REFERENCES usuario(id),
  cargado_en   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, componente, item)
);
CREATE INDEX IF NOT EXISTS cmict_tributo_idx ON cmict_tributo (empresa_id, anio, servicio, componente);

CREATE TABLE IF NOT EXISTS tasa_tua (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio           smallint NOT NULL,
  servicio       text NOT NULL DEFAULT 'acueducto',
  trimestre      text, periodo text, predio text, codigo_predio text,
  concesion      text, fuente text, n_factura text, uso text,
  caudal_lts     double precision, tarifa_unit double precision,
  factor_turno   double precision, factor_op double precision,
  valor          double precision,                -- valor efectivamente pagado de la factura ($)
  resolucion_pago text, fecha_pago text,
  estado         text NOT NULL DEFAULT 'pagado',  -- pagado | pendiente
  observacion    text,
  origen         text NOT NULL DEFAULT 'empresa',
  cargado_por    integer REFERENCES usuario(id),
  cargado_en     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tasa_tua_idx ON tasa_tua (empresa_id, anio, servicio);

CREATE TABLE IF NOT EXISTS tasa_retributiva (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  servicio      text NOT NULL DEFAULT 'alcantarillado',
  punto         text NOT NULL,                    -- punto de vertimiento
  carga_dbo     double precision, carga_sst double precision,   -- kg/año
  tm_dbo        double precision, tm_sst double precision,       -- tarifa mínima $/kg
  fr_liquidado  double precision,                 -- Fr que aplicó la autoridad (por punto)
  total_cfr     double precision,                 -- valor pagado con FR liquidado ($)
  observacion   text,
  origen        text NOT NULL DEFAULT 'empresa',
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, punto)
);
CREATE INDEX IF NOT EXISTS tasa_retributiva_idx ON tasa_retributiva (empresa_id, anio, servicio);

CREATE TABLE IF NOT EXISTS tasa_soporte (
  id           serial PRIMARY KEY,
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio         smallint,
  tipo         text NOT NULL,                     -- tua | retributiva | general
  referencia   text,                              -- n° factura / punto / descripción
  nombre       text NOT NULL,
  tipo_archivo text,
  tamano       integer,
  contenido    bytea NOT NULL,
  subido_por   integer REFERENCES usuario(id),
  subido_en    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tasa_soporte_idx ON tasa_soporte (empresa_id, anio, tipo);

ALTER TABLE cmict_tributo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cmt_all ON cmict_tributo;
CREATE POLICY cmt_all ON cmict_tributo FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

ALTER TABLE tasa_tua ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ttua_all ON tasa_tua;
CREATE POLICY ttua_all ON tasa_tua FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

ALTER TABLE tasa_retributiva ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tret_all ON tasa_retributiva;
CREATE POLICY tret_all ON tasa_retributiva FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

ALTER TABLE tasa_soporte ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tsop_all ON tasa_soporte;
CREATE POLICY tsop_all ON tasa_soporte FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON cmict_tributo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE cmict_tributo_id_seq TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON tasa_tua TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tasa_tua_id_seq TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON tasa_retributiva TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tasa_retributiva_id_seq TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON tasa_soporte TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tasa_soporte_id_seq TO app_user;
