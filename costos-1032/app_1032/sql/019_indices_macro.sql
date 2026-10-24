-- =====================================================================
--  019_indices_macro.sql — varios índices de indexación
--   · ICTC (Índice de Costos del Transporte de Carga, DANE) — mensual,
--     se guarda como columna en indice_ipc (misma grilla año/mes que IPC e IPC-SAR).
--   · Salario mínimo (SMMLV) — anual, tabla propia (se modifica una vez al año).
-- =====================================================================

-- ICTC mensual (número índice), junto a indice (IPC) e ipcs (IPC sin alimentos ni regulados)
ALTER TABLE indice_ipc ADD COLUMN IF NOT EXISTS ictc numeric(14,6);

-- Salario mínimo mensual legal vigente (anual)
CREATE TABLE IF NOT EXISTS salario_minimo (
  anio        smallint PRIMARY KEY,
  valor       numeric(16,4) NOT NULL,          -- SMMLV ($ por mes)
  fuente      text,
  procedencia text DEFAULT 'normativa',        -- normativa (decreto) | supuesto
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE salario_minimo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sm_sel ON salario_minimo;
DROP POLICY IF EXISTS sm_mod ON salario_minimo;
-- de lectura para cualquiera autenticado; lo escribe admin / analista-todas (allow_all)
CREATE POLICY sm_sel ON salario_minimo FOR SELECT USING (true);
CREATE POLICY sm_mod ON salario_minimo FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
GRANT SELECT, INSERT, UPDATE, DELETE ON salario_minimo TO app_user;
