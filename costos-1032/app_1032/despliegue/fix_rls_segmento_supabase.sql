-- =====================================================================
--  REPARA LA LECTURA DE LA TABLA 'segmento' EN SUPABASE
--
--  La asignación automática de segmento (y, al guardar, de r y k_ct) usa la
--  tabla 'segmento'. Si quedó con RLS activo pero sin política de lectura,
--  la app no la puede leer y el segmento no se calcula correctamente.
--  Este script reaplica la política y el permiso. Idempotente.
--  Ejecutar en Supabase → SQL Editor como 'postgres'.
-- =====================================================================
ALTER TABLE segmento ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS seg_sel ON segmento;
CREATE POLICY seg_sel ON segmento FOR SELECT USING (true);

DROP POLICY IF EXISTS seg_mod ON segmento;
CREATE POLICY seg_mod ON segmento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

GRANT SELECT ON segmento TO app_user;

-- Diagnóstico (debe devolver 4):
SELECT count(*) AS segmentos FROM segmento;
