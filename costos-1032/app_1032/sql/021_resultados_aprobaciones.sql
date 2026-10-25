-- =====================================================================
--  021_resultados_aprobaciones.sql
--  (1) resultado_componente_anio: foto de los componentes por AÑO TARIFARIO,
--      para ver CMA/CMO/CMI/CMICT (y el precio) a diciembre de cada año cada
--      que se realiza el recálculo (resultado_componente guarda solo la actual).
--  (2) aprobacion_costos + aprobacion_archivo: soporte del acto administrativo
--      de aprobación de los costos de referencia, por año tarifario.
--  Se ejecuta como el rol dueño.
-- =====================================================================

-- ---------- (1) Histórico de componentes por año tarifario ----------
CREATE TABLE IF NOT EXISTS resultado_componente_anio (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,         -- año tarifario (2026 inicio, 2027 año 1, …)
  servicio      text NOT NULL,             -- acueducto | alcantarillado | —
  componente    text NOT NULL,             -- CMA | CMO | CMI | CMICT | CARGO_FIJO | CARGO_CONSUMO | …
  valor         double precision,
  unidad        text,
  procedencia   text,
  fuente        text,
  articulo      text,
  snapshot_en   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, componente)
);

ALTER TABLE resultado_componente_anio ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rca_all ON resultado_componente_anio;
CREATE POLICY rca_all ON resultado_componente_anio FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON resultado_componente_anio TO app_user;

-- ---------- (2) Aprobaciones de costos de referencia ----------
CREATE TABLE IF NOT EXISTS aprobacion_costos (
  id                  serial PRIMARY KEY,
  empresa_id          integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio_tarifario      smallint NOT NULL,     -- a qué año tarifario corresponde la aprobación
  acto_administrativo text,                  -- número de resolución / acto administrativo
  fecha_aprobacion    date,
  observacion         text,
  creado_por          integer REFERENCES usuario(id),
  creado_en           timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE aprobacion_costos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS apc_all ON aprobacion_costos;
CREATE POLICY apc_all ON aprobacion_costos FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON aprobacion_costos TO app_user;

CREATE TABLE IF NOT EXISTS aprobacion_archivo (
  id            serial PRIMARY KEY,
  aprobacion_id integer NOT NULL REFERENCES aprobacion_costos(id) ON DELETE CASCADE,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  nombre        text NOT NULL,              -- nombre original del archivo
  tipo          text,                       -- extensión/tipo (pdf, xlsx, png…)
  tamano        integer,                    -- bytes
  contenido     bytea NOT NULL,
  subido_por    integer REFERENCES usuario(id),
  subido_en     timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE aprobacion_archivo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS apa_all ON aprobacion_archivo;
CREATE POLICY apa_all ON aprobacion_archivo FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON aprobacion_archivo TO app_user;

-- Uso de las secuencias serial para que app_user pueda insertar.
GRANT USAGE, SELECT ON SEQUENCE
  resultado_componente_anio_id_seq, aprobacion_costos_id_seq, aprobacion_archivo_id_seq TO app_user;
