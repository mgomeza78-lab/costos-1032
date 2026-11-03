-- =====================================================================
--  047_poir_plan.sql — POIR 688 PLANEADO (inicial y actualizado art. 52).
--
--  Guarda el plan de obras e inversiones del POIR en sus dos versiones:
--    tipo='ini'  → POIR inicial (06_1 del modelo), plan original.
--    tipo='act'  → POIR actualizado (06_2), ajustado conforme al art. 52 de la
--                  Res. CRA 688/2014; es el referente de la comparación vs. ejecutado.
--  Es INFORMATIVO: los resultados (VPR₀/VA₀/CMI de referencia) se calculan sobre el
--  POIR EJECUTADO (cmi_proyecto, tipo='poir'), no sobre el plan. Admite varias filas
--  por id_activo (el actualizado viene desagregado), por eso usa id serial.
--  Idempotente.
-- =====================================================================

CREATE TABLE IF NOT EXISTS poir_plan (
  id              bigserial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  tipo            text NOT NULL,            -- 'ini' | 'act'
  servicio        text NOT NULL,            -- acueducto | alcantarillado
  id_activo       text,
  codigo_poir     text,
  subsistema      text,
  actividad       text,
  nombre          text,
  anio_planeado   integer,                  -- año planeado (ini) / año de ejecución real (act)
  vida_util       double precision,
  valor_poir      double precision,         -- valor POIR del activo ($dic-2014)
  vp_poir         double precision,         -- VP de los ingresos del activo ($dic-2014)
  cmi             double precision,         -- CMI_POIR del activo ($/m³ dic-2014)
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_poirplan ON poir_plan(empresa_id, tipo, servicio);

ALTER TABLE poir_plan ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poirplan_all ON poir_plan;
CREATE POLICY poirplan_all ON poir_plan FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON poir_plan TO app_user;
GRANT USAGE, SELECT ON SEQUENCE poir_plan_id_seq TO app_user;
