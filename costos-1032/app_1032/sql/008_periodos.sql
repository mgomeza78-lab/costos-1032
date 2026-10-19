-- =====================================================================
--  008_periodos.sql — catálogo de AÑOS TARIFARIOS (Res. CRA 1032/2026).
--  Período de inicio (jul-dic 2026) + años tarifarios 1..10 (2027..2036).
--  Fija el marco temporal del cargue de información. Catálogo común (lectura
--  para todos). Fuente canónica en periodos.py. Rol dueño (postgres).
-- =====================================================================
CREATE TABLE IF NOT EXISTS ano_tarifario (
  clave     text PRIMARY KEY,          -- inicio | a1..a10
  orden     smallint NOT NULL,
  etiqueta  text NOT NULL,             -- 'Período de inicio' | 'Año tarifario N'
  corto     text NOT NULL,
  anio      smallint NOT NULL UNIQUE,  -- año calendario
  mes_ini   smallint NOT NULL,
  mes_fin   smallint NOT NULL,
  fecha_ini date NOT NULL,
  fecha_fin date NOT NULL,
  es_inicio boolean NOT NULL DEFAULT false,
  meses     smallint NOT NULL
);

INSERT INTO ano_tarifario(clave,orden,etiqueta,corto,anio,mes_ini,mes_fin,fecha_ini,fecha_fin,es_inicio,meses) VALUES
  ('inicio',0,'Período de inicio','Inicio',2026,7,12,'2026-07-01','2026-12-31',true,6),
  ('a1',1,'Año tarifario 1','Año 1',2027,1,12,'2027-01-01','2027-12-31',false,12),
  ('a2',2,'Año tarifario 2','Año 2',2028,1,12,'2028-01-01','2028-12-31',false,12),
  ('a3',3,'Año tarifario 3','Año 3',2029,1,12,'2029-01-01','2029-12-31',false,12),
  ('a4',4,'Año tarifario 4','Año 4',2030,1,12,'2030-01-01','2030-12-31',false,12),
  ('a5',5,'Año tarifario 5','Año 5',2031,1,12,'2031-01-01','2031-12-31',false,12),
  ('a6',6,'Año tarifario 6','Año 6',2032,1,12,'2032-01-01','2032-12-31',false,12),
  ('a7',7,'Año tarifario 7','Año 7',2033,1,12,'2033-01-01','2033-12-31',false,12),
  ('a8',8,'Año tarifario 8','Año 8',2034,1,12,'2034-01-01','2034-12-31',false,12),
  ('a9',9,'Año tarifario 9','Año 9',2035,1,12,'2035-01-01','2035-12-31',false,12),
  ('a10',10,'Año tarifario 10','Año 10',2036,1,12,'2036-01-01','2036-12-31',false,12)
ON CONFLICT (clave) DO UPDATE SET etiqueta=excluded.etiqueta, corto=excluded.corto,
  anio=excluded.anio, fecha_ini=excluded.fecha_ini, fecha_fin=excluded.fecha_fin,
  es_inicio=excluded.es_inicio, meses=excluded.meses;

ALTER TABLE ano_tarifario ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS at_sel ON ano_tarifario;  DROP POLICY IF EXISTS at_mod ON ano_tarifario;
CREATE POLICY at_sel ON ano_tarifario FOR SELECT USING (true);
CREATE POLICY at_mod ON ano_tarifario FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
GRANT SELECT, INSERT, UPDATE, DELETE ON ano_tarifario TO app_user;
