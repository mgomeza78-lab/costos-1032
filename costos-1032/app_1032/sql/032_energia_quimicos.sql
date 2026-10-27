-- =====================================================================
--  032_energia_quimicos.sql — Costos operativos particulares de ENERGÍA (CE)
--  e INSUMOS QUÍMICOS (CIQ), al detalle del modelo (art. 2.1.2.1.3.4.6 y
--  el de insumos químicos). Permiten el cálculo bottom-up del CMO:
--    · energia_punto : una fila por punto de toma/bombeo. Ceb = Keb·Pce,
--        Keb = mín[(Υ/(3600·η))·V·H , Kr]; η depende del volumen (acueducto)
--        o es 0,60 (alcantarillado). El sistema calcula FE, teórico, Keb,
--        Ceb y el castigo por eficiencia; aquí solo se guardan las ENTRADAS.
--    · quimico_item  : una fila por insumo/planta. CIQ = Piq·Σ(kg ene–dic).
--  Dos vías de cargue (manual o masivo con plantilla), como el resto.
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

CREATE TABLE IF NOT EXISTS energia_punto (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio            smallint NOT NULL,
  servicio        text NOT NULL,                       -- acueducto | alcantarillado
  tipo            text NOT NULL DEFAULT 'bombeo',       -- bombeo (fórmula hidráulica) | otros (Ce = Ko·Pce)
  no_sui          text NOT NULL DEFAULT '',
  punto           text NOT NULL,                        -- punto de toma/bombeo j
  actividad       text NOT NULL DEFAULT '',             -- producción | distribución | ...
  volumen_m3      double precision,                     -- Vⱼ (m³/año); en 'otros' no aplica
  altura_m        double precision,                     -- Hⱼ (m)
  consumo_real_kwh double precision,                    -- Krⱼ (kWh/año)
  precio_kwh      double precision,                     -- Pceⱼ ($/kWh)
  eta_reporte     double precision,                     -- η del reporte (comparativo, opcional)
  observacion     text,
  origen          text NOT NULL DEFAULT 'empresa',
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, no_sui, punto)
);
ALTER TABLE energia_punto ADD COLUMN IF NOT EXISTS tipo text NOT NULL DEFAULT 'bombeo';
CREATE INDEX IF NOT EXISTS energia_punto_idx ON energia_punto (empresa_id, anio, servicio);

CREATE TABLE IF NOT EXISTS quimico_item (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio            smallint NOT NULL,
  servicio        text NOT NULL,                       -- acueducto | alcantarillado
  no_sui          text NOT NULL DEFAULT '',
  punto           text NOT NULL DEFAULT '',             -- planta o punto
  insumo          text NOT NULL,                        -- insumo químico
  estado          text NOT NULL DEFAULT '',             -- líquido | gaseoso | sólido
  precio_kg       double precision,                     -- Piq ($/kg)
  m1  double precision DEFAULT 0, m2  double precision DEFAULT 0,
  m3  double precision DEFAULT 0, m4  double precision DEFAULT 0,
  m5  double precision DEFAULT 0, m6  double precision DEFAULT 0,
  m7  double precision DEFAULT 0, m8  double precision DEFAULT 0,
  m9  double precision DEFAULT 0, m10 double precision DEFAULT 0,
  m11 double precision DEFAULT 0, m12 double precision DEFAULT 0,
  observacion     text,
  origen          text NOT NULL DEFAULT 'empresa',
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, punto, insumo)
);
CREATE INDEX IF NOT EXISTS quimico_item_idx ON quimico_item (empresa_id, anio, servicio);

ALTER TABLE energia_punto ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS enp_all ON energia_punto;
CREATE POLICY enp_all ON energia_punto FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

ALTER TABLE quimico_item ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS qim_all ON quimico_item;
CREATE POLICY qim_all ON quimico_item FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON energia_punto TO app_user;
GRANT USAGE, SELECT ON SEQUENCE energia_punto_id_seq TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON quimico_item TO app_user;
GRANT USAGE, SELECT ON SEQUENCE quimico_item_id_seq TO app_user;
