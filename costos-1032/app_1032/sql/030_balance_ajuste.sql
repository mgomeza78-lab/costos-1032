-- =====================================================================
--  030_balance_ajuste.sql — Ajustes MANUALES del balance (Res. CRA 1032):
--   · desagregaciones del CAC por numeral (CAC-4 gestión social PQRS/Comités,
--     CAC-5 iniciativas de gestión social IDH7/IDH14, CAC-6 inversiones
--     ambientales administrativas) — art. 2.1.2.1.3.2.4. Son DESAGREGACIONES
--     (ya incluidas en el balance), se muestran aparte; en el período de inicio
--     no cambian el total (PE=100%), pero se identifican para el recálculo.
--   · exclusiones explícitas (art. 2.1.2.1.3.3.3): costos con ingreso asociado,
--     actividades no reguladas, etc. SE RESTAN del numerador reconocido.
--  Cubetas ac_dir/al_dir/repartir como el resto (repartir = por el %). La
--  contabilidad no separa estos conceptos → entrada manual. Idempotente; RLS.
-- =====================================================================

CREATE TABLE IF NOT EXISTS balance_ajuste (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio        smallint NOT NULL,
  tipo        text NOT NULL,                 -- CAC-4 | CAC-5 | CAC-6 | exclusion
  componente  text NOT NULL,                 -- CMA (4/5/6) | CMA/CMO/CMICT (exclusion)
  concepto    text NOT NULL,
  cod_dane    text NOT NULL DEFAULT '',
  ac_dir      double precision NOT NULL DEFAULT 0,
  al_dir      double precision NOT NULL DEFAULT 0,
  repartir    double precision NOT NULL DEFAULT 0,
  observacion text,
  creado_por  integer REFERENCES usuario(id),
  creado_en   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS balance_ajuste_idx ON balance_ajuste (empresa_id, anio, tipo, componente);

ALTER TABLE balance_ajuste ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS baj_all ON balance_ajuste;
CREATE POLICY baj_all ON balance_ajuste FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON balance_ajuste TO app_user;
GRANT USAGE, SELECT ON SEQUENCE balance_ajuste_id_seq TO app_user;
