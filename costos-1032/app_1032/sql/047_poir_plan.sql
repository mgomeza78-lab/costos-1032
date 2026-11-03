-- =====================================================================
--  047_poir_plan.sql — POIR 688 PLANEADO por TRAMO.
--
--  Guarda el plan de obras e inversiones del POIR, UNA VERSIÓN POR TRAMO del
--  CMI_POIR definido en Agua facturada (Paso 1). El nº de tramos = nº de
--  modificaciones del POIR durante la 688 + 1:
--    tramo 1       → POIR inicial (06_1 del modelo), plan original.
--    tramo 2..N    → POIR actualizado tras cada modificación (art. 52 Res. 688);
--                    el último es el referente de la comparación vs. ejecutado.
--  El usuario puede cargar tantos tramos como tenga el CMI_POIR en el Paso 1.
--  Validación (igual que el ejecutado/BCR): por servicio y tramo,
--    Σ cmi individual = CMI_POIR total del tramo (Paso 1).
--  Es INFORMATIVO: los resultados (VPR₀/VA₀/CMI de referencia) se calculan sobre
--  el POIR EJECUTADO (cmi_proyecto, tipo='poir'), no sobre el plan. Admite varias
--  filas por id_activo (el actualizado viene desagregado), por eso usa id serial.
--  Idempotente.
-- =====================================================================

CREATE TABLE IF NOT EXISTS poir_plan (
  id              bigserial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  tramo           smallint NOT NULL DEFAULT 1,   -- 1 = inicial; 2..N = actualizaciones
  servicio        text NOT NULL,                 -- acueducto | alcantarillado
  id_activo       text,
  codigo_poir     text,
  subsistema      text,
  actividad       text,
  nombre          text,
  anio_planeado   integer,                        -- año planeado (tramo 1) / año de ejecución (tramos 2+)
  vida_util       double precision,
  valor_poir      double precision,               -- valor POIR del activo ($dic-2014)
  vp_poir         double precision,               -- VP de los ingresos del activo ($dic-2014)
  cmi             double precision,               -- CMI_POIR del activo ($/m³ dic-2014)
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now()
);
-- Idempotente para una versión previa de esta tabla (que usaba 'tipo'):
ALTER TABLE poir_plan ADD COLUMN IF NOT EXISTS tramo smallint NOT NULL DEFAULT 1;
ALTER TABLE poir_plan ALTER COLUMN tramo DROP DEFAULT;
ALTER TABLE poir_plan DROP COLUMN IF EXISTS tipo;
CREATE INDEX IF NOT EXISTS ix_poirplan ON poir_plan(empresa_id, tramo, servicio);

ALTER TABLE poir_plan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poirplan_all ON poir_plan;
CREATE POLICY poirplan_all ON poir_plan FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON poir_plan TO app_user;
GRANT USAGE, SELECT ON SEQUENCE poir_plan_id_seq TO app_user;
