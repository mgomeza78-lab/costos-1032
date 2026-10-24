-- =====================================================================
--  Supabase — varios índices de indexación (ICTC mensual + SMMLV anual)
--  Correr UNA VEZ en el SQL Editor de Supabase. Idempotente.
--  No borra ni modifica datos existentes de IPC / IPC-SAR.
-- =====================================================================

-- 1) ICTC mensual (número índice), junto a indice (IPC) e ipcs (IPC-SAR)
ALTER TABLE indice_ipc ADD COLUMN IF NOT EXISTS ictc numeric(14,6);

-- 2) Salario mínimo (SMMLV) — anual
CREATE TABLE IF NOT EXISTS salario_minimo (
  anio        smallint PRIMARY KEY,
  valor       numeric(16,4) NOT NULL,          -- SMMLV ($ por mes)
  fuente      text,
  procedencia text DEFAULT 'normativa',
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE salario_minimo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sm_sel ON salario_minimo;
DROP POLICY IF EXISTS sm_mod ON salario_minimo;
CREATE POLICY sm_sel ON salario_minimo FOR SELECT USING (true);
CREATE POLICY sm_mod ON salario_minimo FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
GRANT SELECT, INSERT, UPDATE, DELETE ON salario_minimo TO app_user;

-- 3) Verificación (debe devolver: ictc=1, salario_minimo=1)
SELECT
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='indice_ipc' AND column_name='ictc')          AS col_ictc,
  (CASE WHEN to_regclass('public.salario_minimo') IS NOT NULL
        THEN 1 ELSE 0 END)                                          AS tabla_salario_minimo;
