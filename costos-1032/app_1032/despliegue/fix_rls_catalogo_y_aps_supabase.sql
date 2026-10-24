-- =====================================================================
--  REPARA LA LECTURA DEL CATÁLOGO DIVIPOLA Y DE LOS APS EN SUPABASE
--
--  Síntoma: al crear/editar una empresa, el cuadro de municipios aparece
--  vacío aunque exista el catálogo (1.122 municipios); y la configuración
--  de APS de las empresas ya creadas no se ve.
--
--  Causa: estas tablas quedaron con Row-Level Security ACTIVO pero SIN sus
--  políticas de lectura, por lo que devuelven 0 filas (RLS niega por
--  defecto). El desplegable de departamentos sí funciona porque su política
--  sí está. Este script reaplica las políticas y los permisos que definen
--  las migraciones 010 (territorio) y 012 (APS).
--
--  Es IDEMPOTENTE: se puede ejecutar varias veces sin dañar nada.
--  Ejecútalo en Supabase → SQL Editor, conectado como 'postgres'.
-- =====================================================================

-- ---------- Catálogo DIVIPOLA y municipios por empresa (migración 010) ----------
ALTER TABLE departamento      ENABLE ROW LEVEL SECURITY;
ALTER TABLE municipio         ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresa_municipio ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS dpto_sel ON departamento;
CREATE POLICY dpto_sel ON departamento FOR SELECT USING (true);
DROP POLICY IF EXISTS dpto_mod ON departamento;
CREATE POLICY dpto_mod ON departamento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

DROP POLICY IF EXISTS mun_sel ON municipio;
CREATE POLICY mun_sel ON municipio FOR SELECT USING (true);
DROP POLICY IF EXISTS mun_mod ON municipio;
CREATE POLICY mun_mod ON municipio FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

DROP POLICY IF EXISTS em_all ON empresa_municipio;
CREATE POLICY em_all ON empresa_municipio FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON departamento, municipio, empresa_municipio TO app_user;

-- ---------- APS y sus soportes (migración 012) ----------
ALTER TABLE aps         ENABLE ROW LEVEL SECURITY;
ALTER TABLE aps_archivo ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS aps_all ON aps;
CREATE POLICY aps_all ON aps FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS apsarch_all ON aps_archivo;
CREATE POLICY apsarch_all ON aps_archivo FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON aps, aps_archivo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE aps_id_seq, aps_archivo_id_seq TO app_user;

-- ---------- Diagnóstico (debe mostrar 1122 / 33 / 1122) ----------
SELECT (SELECT count(*) FROM municipio)    AS municipios,
       (SELECT count(*) FROM departamento) AS departamentos,
       (SELECT count(*) FROM municipio m JOIN departamento d ON d.cod_dane = m.cod_dpto) AS municipios_enlazados;
