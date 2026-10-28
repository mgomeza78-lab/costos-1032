-- =====================================================================
--  041_metas_eval.sql — Metas mixtas con evaluación de cumplimiento (Cap. 2, arts.
--  2.1.2.1.2.1 / 2.1.2.1.2.2 / 2.1.2.1.2.3).
--
--  (1) meta_catalogo += objetivo estructurado (cuantitativa/objetivo_num/unidad/sentido)
--      para que el sistema pueda EVALUAR el nivel de cumplimiento de los estándares
--      numéricos (los cualitativos se evalúan por estado). Valores por el SEGUNDO SEGMENTO.
--  (2) meta_propia : metas que define la EMPRESA (además de las reguladas).
--  (3) meta_seguimiento : valor REAL del indicador por año tarifario (el usuario lo ingresa;
--      el sistema calcula el cumplimiento). Sirve para reguladas y propias.
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

-- (1) Objetivo estructurado en el catálogo regulado -------------------
ALTER TABLE meta_catalogo ADD COLUMN IF NOT EXISTS cuantitativa boolean NOT NULL DEFAULT false;
ALTER TABLE meta_catalogo ADD COLUMN IF NOT EXISTS objetivo_num double precision;  -- valor meta del estándar
ALTER TABLE meta_catalogo ADD COLUMN IF NOT EXISTS unidad text;                    -- %, h/día, m³/suscriptor·mes…
ALTER TABLE meta_catalogo ADD COLUMN IF NOT EXISTS sentido text;                   -- ge (≥ mejor) | le (≤ mejor) | eq

-- Estándares numéricos del segundo segmento (dirección de cumplimiento explícita).
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=100, unidad='%',           sentido='ge' WHERE codigo='IDH1'  AND servicio='acueducto';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=24,  unidad='h/día',       sentido='ge' WHERE codigo='IDH2'  AND servicio='acueducto';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=4,   unidad='puntaje',     sentido='ge' WHERE codigo='IDH6'  AND servicio='acueducto';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=4,   unidad='m³/suscriptor·mes', sentido='le' WHERE codigo='IRD1' AND servicio='acueducto';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=100, unidad='%',           sentido='ge' WHERE codigo='IDH8'  AND servicio='alcantarillado';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=100, unidad='%',           sentido='ge' WHERE codigo='IDH9'  AND servicio='alcantarillado';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=68,  unidad='%',           sentido='ge' WHERE codigo='IDH11' AND servicio='alcantarillado';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=100, unidad='%',           sentido='ge' WHERE codigo='IDH12' AND servicio='alcantarillado';
UPDATE meta_catalogo SET cuantitativa=true, objetivo_num=4,   unidad='puntaje',     sentido='ge' WHERE codigo='IDH13' AND servicio='alcantarillado';

-- (2) Metas definidas por la empresa ---------------------------------
CREATE TABLE IF NOT EXISTS meta_propia (
  id           serial PRIMARY KEY,
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio     text NOT NULL,                 -- acueducto | alcantarillado
  codigo       text,                          -- código libre de la empresa
  nombre       text NOT NULL,
  descripcion  text,
  cuantitativa boolean NOT NULL DEFAULT false,
  objetivo_num double precision,
  unidad       text,
  sentido      text,                          -- ge | le | eq
  creado_por   integer REFERENCES usuario(id),
  creado_en    timestamptz NOT NULL DEFAULT now(),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);
CREATE INDEX IF NOT EXISTS meta_propia_idx ON meta_propia(empresa_id, servicio);

ALTER TABLE meta_propia ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mp_all ON meta_propia;
CREATE POLICY mp_all ON meta_propia FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- (3) Seguimiento del valor REAL por año tarifario -------------------
--  origen = 'regulacion' (ref_id → meta_catalogo.id) | 'propia' (ref_id → meta_propia.id)
CREATE TABLE IF NOT EXISTS meta_seguimiento (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  origen        text NOT NULL DEFAULT 'regulacion',
  ref_id        integer NOT NULL,              -- id de la meta (catálogo o propia) según `origen`
  anio_tarifario smallint NOT NULL,            -- año de aplicación (2027…)
  valor_real    double precision,              -- valor medido del indicador (lo ingresa el usuario)
  estado        text,                          -- para cualitativas o anulación manual
  observacion   text,
  actualizado_por integer REFERENCES usuario(id),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, origen, ref_id, anio_tarifario),
  CHECK (origen IN ('regulacion','propia'))
);
CREATE INDEX IF NOT EXISTS meta_seg_idx ON meta_seguimiento(empresa_id, anio_tarifario);

ALTER TABLE meta_seguimiento ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ms_all ON meta_seguimiento;
CREATE POLICY ms_all ON meta_seguimiento FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON meta_propia, meta_seguimiento TO app_user;
GRANT USAGE, SELECT ON SEQUENCE meta_propia_id_seq, meta_seguimiento_id_seq TO app_user;
