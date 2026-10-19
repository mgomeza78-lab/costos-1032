-- =====================================================================
--  004_operacion.sql — capa de operación mensual.
--  Índice IPC (referencia nacional cargada), carga mensual ampliada y
--  tarifa vigente por empresa/mes/servicio (resultado del motor de gatillo).
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- ---------- Índice IPC mensual (referencia nacional; DATO CARGADO, no inventado) ----------
CREATE TABLE IF NOT EXISTS indice_ipc (
  anio        smallint NOT NULL,
  mes         smallint NOT NULL,
  indice      numeric(14,6) NOT NULL,       -- número índice IPC (base DANE)
  fuente      text,
  procedencia text DEFAULT 'SUI/DANE',      -- normativa | reportada | SUI | supuesto
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (anio, mes)
);

-- ---------- Ampliar la carga mensual ----------
ALTER TABLE carga_mensual ADD COLUMN IF NOT EXISTS facturacion double precision;
ALTER TABLE carga_mensual ADD COLUMN IF NOT EXISTS novedades   text;

-- ---------- Tarifa vigente mensual (salida del motor de indexación) ----------
CREATE TABLE IF NOT EXISTS tarifa_vigente (
  id               serial PRIMARY KEY,
  empresa_id       integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio             smallint NOT NULL,
  mes              smallint NOT NULL,
  servicio         text NOT NULL,
  cargo_fijo       double precision,
  cargo_consumo    double precision,
  factor_acumulado double precision,        -- respecto a la base del período de inicio
  variacion_acum   double precision,        -- variación IPC acumulada desde la última indexación
  indexado         boolean NOT NULL DEFAULT false,   -- el gatillo disparó este mes
  calculado_en     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);
CREATE INDEX IF NOT EXISTS ix_tv_empresa ON tarifa_vigente(empresa_id);

-- ---------- RLS ----------
ALTER TABLE indice_ipc     ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarifa_vigente ENABLE ROW LEVEL SECURITY;

-- IPC: lo lee cualquiera autenticado; lo escribe admin / analista-todas (allow_all)
DROP POLICY IF EXISTS ipc_sel ON indice_ipc;  DROP POLICY IF EXISTS ipc_mod ON indice_ipc;
CREATE POLICY ipc_sel ON indice_ipc FOR SELECT USING (true);
CREATE POLICY ipc_mod ON indice_ipc FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

-- tarifa_vigente: por empresa permitida
DROP POLICY IF EXISTS tv_all ON tarifa_vigente;
CREATE POLICY tv_all ON tarifa_vigente FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants para las tablas nuevas (los GRANT previos no las cubren) ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON indice_ipc, tarifa_vigente TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tarifa_vigente_id_seq TO app_user;
