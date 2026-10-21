-- =====================================================================
--  014_bcr0_inicio.sql — Reconstrucción de la BCR₀ de inicio de la 1032.
--
--  Núcleo de variables para calcular la BCR₀ a partir del marco anterior
--  (Res. 688/825): parámetros de reconstrucción por servicio (bcr_param),
--  series de agua facturada y CMI cobrado por año tarifario de la 688
--  (bcr_serie) y las variables de la cadena del VA₀ por activo
--  (ampliación de bcr_activo). Arts. 2.1.2.1.3.5.3 a .7, .11, .13, .18 y
--  2.1.2.1.5.2.1.1. Rol dueño (postgres).
-- =====================================================================

-- ---------- Parámetros de reconstrucción 688 por servicio ----------
CREATE TABLE IF NOT EXISTS bcr_param (
  empresa_id       integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio         text NOT NULL,
  r688             double precision,          -- tasa de descuento de la Res. 688
  ipc_dic_2014     double precision,          -- IPC dic-2014 (para fa0)
  ipc_dic_2025     double precision,          -- IPC dic-2025 (para fa0)
  fecha_inicio_688 date,                       -- inicio de aplicación de la 688 (→ t a 30-jun-2026)
  provision_poir   double precision,          -- saldo provisión POIR no ejecutado (Res. 950, 30-jun-2026)
  ccp_2025         double precision,          -- CCP 2025 (m³/año) para dividir el CI → CMI_BCR
  observacion      text,
  actualizado_en   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, servicio),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- Series por año tarifario de la 688 (agua facturada y CMI cobrado) ----------
CREATE TABLE IF NOT EXISTS bcr_serie (
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio       text NOT NULL,
  anio_tarifario smallint NOT NULL,           -- 1..10 de aplicación de la 688
  q_m3           double precision,            -- agua facturada en el año (m³)
  cmi_cobrado    double precision,            -- CMI688 efectivamente cobrado ($/m³)
  PRIMARY KEY (empresa_id, servicio, anio_tarifario),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- Variables de la cadena del VA₀ por activo ----------
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS tipo_activo     text;        -- subsistema/actividad/tipo
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vida_util       numeric(6,2);-- VU
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS via688          double precision;  -- VIA688ⱼ ($dic-2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vp_cmi_q        double precision;  -- VP(CMI688×Q) recuperado
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vpr0            double precision;  -- VPR₀ = VIA − VP(CMI×Q) ($dic-2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS va0             double precision;  -- VA₀ ($dic-2025) antes de compensar
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS anio_poir       smallint;    -- año tarifario de entrada en operación (POIR)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS ejecucion_real  double precision;  -- valor ejecutado real POIR ($2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS fecha_operacion date;        -- fecha real de operación (POIR)

-- ---------- RLS ----------
ALTER TABLE bcr_param ENABLE ROW LEVEL SECURITY;
ALTER TABLE bcr_serie ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bcrparam_all ON bcr_param;
CREATE POLICY bcrparam_all ON bcr_param FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS bcrserie_all ON bcr_serie;
CREATE POLICY bcrserie_all ON bcr_serie FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON bcr_param, bcr_serie TO app_user;
