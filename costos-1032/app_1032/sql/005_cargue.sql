-- =====================================================================
--  005_cargue.sql — cargue mensual por clase, factores, indicadores,
--  factura teórica por estrato (derivada) y segunda canasta de indexación.
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- IPCs (índice de precios específicos) para CMA/CMO/CMICT; indice (IPC) ya existe (CMI).
ALTER TABLE indice_ipc ADD COLUMN IF NOT EXISTS ipcs numeric(14,6);

-- Segunda canasta en la tarifa vigente: variación/indexación por IPC (CMI).
ALTER TABLE tarifa_vigente ADD COLUMN IF NOT EXISTS var_ipc      double precision;
ALTER TABLE tarifa_vigente ADD COLUMN IF NOT EXISTS indexado_ipc boolean NOT NULL DEFAULT false;

-- ---------- Detalle comercial por clase (formulario SUI 6080/6081) ----------
CREATE TABLE IF NOT EXISTS carga_mensual_detalle (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio           smallint NOT NULL,
  mes            smallint NOT NULL,
  servicio       text NOT NULL,            -- AC | AL (o acueducto/alcantarillado)
  clase          smallint NOT NULL,        -- clase de uso SUI (1-6 estratos; 10-13 no residencial)
  suscriptores   integer,
  m3             double precision,
  m3_subsidiable double precision,
  origen         text,                     -- SUI | archivo_propio | muestra
  cargado_por    integer REFERENCES usuario(id),
  cargado_en     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, clase)
);

-- ---------- Factores de subsidio/contribución por clase (SUI 1051/1114) ----------
CREATE TABLE IF NOT EXISTS factor_subsidio (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  vigencia        smallint NOT NULL,
  servicio        text NOT NULL,
  clase           smallint NOT NULL,
  factor_cargofijo double precision,       -- subsidio (-) / contribución (+)
  factor_consumo   double precision,
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, vigencia, servicio, clase)
);

-- ---------- Indicadores mensuales (6084 SURICATA, etc.) ----------
CREATE TABLE IF NOT EXISTS indicador_mensual (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  mes           smallint NOT NULL,
  servicio      text NOT NULL,
  ipuf_real     double precision,
  continuidad_h double precision,
  irca          double precision,
  reclamaciones integer,
  cortes        integer,
  reconexiones  integer,
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);

-- ---------- Factura teórica por clase (DERIVADA) ----------
CREATE TABLE IF NOT EXISTS factura_clase (
  id                    serial PRIMARY KEY,
  empresa_id            integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio                  smallint NOT NULL,
  mes                   smallint NOT NULL,
  servicio              text NOT NULL,
  clase                 smallint NOT NULL,
  suscriptores          integer,
  m3                    double precision,
  m3_subsidiable        double precision,
  cf_facturado          double precision,
  cc_facturado          double precision,
  subsidio_contribucion double precision,
  factura_total         double precision,
  calculado_en          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, clase)
);

CREATE INDEX IF NOT EXISTS ix_cmd_emp ON carga_mensual_detalle(empresa_id);
CREATE INDEX IF NOT EXISTS ix_fac_emp ON factura_clase(empresa_id);

-- ---------- RLS por empresa en las nuevas tablas ----------
ALTER TABLE carga_mensual_detalle ENABLE ROW LEVEL SECURITY;
ALTER TABLE factor_subsidio       ENABLE ROW LEVEL SECURITY;
ALTER TABLE indicador_mensual     ENABLE ROW LEVEL SECURITY;
ALTER TABLE factura_clase         ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cmd_all ON carga_mensual_detalle;
CREATE POLICY cmd_all ON carga_mensual_detalle FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS fs_all ON factor_subsidio;
CREATE POLICY fs_all ON factor_subsidio FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS im_all ON indicador_mensual;
CREATE POLICY im_all ON indicador_mensual FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS fc_all ON factura_clase;
CREATE POLICY fc_all ON factura_clase FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE
  ON carga_mensual_detalle, factor_subsidio, indicador_mensual, factura_clase TO app_user;
GRANT USAGE, SELECT ON SEQUENCE
  carga_mensual_detalle_id_seq, factor_subsidio_id_seq,
  indicador_mensual_id_seq, factura_clase_id_seq TO app_user;
