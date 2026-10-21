-- =====================================================================
--  010_territorio.sql — Territorio (DIVIPOLA), segmentación 1032 y campos
--  de alta de empresa. Se ejecuta como el rol dueño (postgres).
--
--  - Catálogo DIVIPOLA del DANE: departamento y municipio.
--  - empresa_municipio: una empresa puede atender varios municipios
--    (prestadores regionales).
--  - empresa += codigo_sui, n_aps, suscriptores_seg.
--  - Los 4 segmentos de la Res. CRA 1032 (art. 2.1.2.1.1.6), con sus tasas
--    r (art. 2.1.2.1.3.1.7) y kct (art. 2.1.2.1.3.1.8).
-- =====================================================================

-- ---------- Catálogo DIVIPOLA ----------
CREATE TABLE IF NOT EXISTS departamento (
  cod_dane char(2) PRIMARY KEY,          -- código DANE del departamento (p. ej. '41')
  nombre   text NOT NULL
);

CREATE TABLE IF NOT EXISTS municipio (
  cod_dane char(5) PRIMARY KEY,          -- código DANE del municipio (incluye el del depto; '41001')
  cod_dpto char(2) NOT NULL REFERENCES departamento(cod_dane),
  nombre   text NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mun_dpto ON municipio(cod_dpto);

-- ---------- Municipios atendidos por cada empresa (varios) ----------
CREATE TABLE IF NOT EXISTS empresa_municipio (
  empresa_id integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  cod_dane   char(5) NOT NULL REFERENCES municipio(cod_dane),
  PRIMARY KEY (empresa_id, cod_dane)
);
CREATE INDEX IF NOT EXISTS ix_em_empresa ON empresa_municipio(empresa_id);

-- ---------- Campos nuevos de empresa ----------
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS codigo_sui       text;      -- código/ID del prestador en el SUI
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS n_aps            smallint;  -- número de Áreas de Prestación del Servicio
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS suscriptores_seg integer;   -- suscriptores al 31-dic-2024 usados para el segmento

-- ---------- RLS ----------
ALTER TABLE departamento      ENABLE ROW LEVEL SECURITY;
ALTER TABLE municipio         ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresa_municipio ENABLE ROW LEVEL SECURITY;

-- catálogo: lo lee cualquier autenticado; lo escribe admin/analista-todas (allow_all)
DROP POLICY IF EXISTS dpto_sel ON departamento; DROP POLICY IF EXISTS dpto_mod ON departamento;
CREATE POLICY dpto_sel ON departamento FOR SELECT USING (true);
CREATE POLICY dpto_mod ON departamento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS mun_sel ON municipio; DROP POLICY IF EXISTS mun_mod ON municipio;
CREATE POLICY mun_sel ON municipio FOR SELECT USING (true);
CREATE POLICY mun_mod ON municipio FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

-- empresa_municipio: por empresa permitida
DROP POLICY IF EXISTS em_all ON empresa_municipio;
CREATE POLICY em_all ON empresa_municipio FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON departamento, municipio, empresa_municipio TO app_user;

-- ---------- Segmentos CRA 1032 (art. 2.1.2.1.1.6; r: 2.1.2.1.3.1.7; kct: 2.1.2.1.3.1.8) ----------
INSERT INTO segmento (id,nombre,susc_min,susc_max,r,kct,ipuf_estrella,articulo_r,articulo_kct) VALUES
 (1,'Primer segmento (> 300.000 suscriptores)',       300001, NULL,   0.0858, 0.0178, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (2,'Segundo segmento (90.001 – 300.000 suscriptores)', 90001, 300000, 0.0903, 0.0154, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (3,'Tercer segmento (17.001 – 90.000 suscriptores)',   17001, 90000,  0.0910, 0.0162, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (4,'Cuarto segmento (5.001 – 17.000 suscriptores)',     5001, 17000,  0.0910, 0.0203, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8')
ON CONFLICT (id) DO UPDATE SET nombre=excluded.nombre, susc_min=excluded.susc_min,
 susc_max=excluded.susc_max, r=excluded.r, kct=excluded.kct, ipuf_estrella=excluded.ipuf_estrella,
 articulo_r=excluded.articulo_r, articulo_kct=excluded.articulo_kct;

-- ---------- DIVIPOLA (departamentos y municipios) ----------
-- Los datos (33 departamentos y los 1.122 municipios del DANE) se cargan en la
-- migración 011_divipola_data.sql, como tabla fija del sistema.
