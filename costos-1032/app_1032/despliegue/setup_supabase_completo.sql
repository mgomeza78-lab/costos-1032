-- =====================================================================
-- SETUP COMPLETO EN SUPABASE — ejecutar todo de una vez (SQL Editor).
-- Reúne, en orden: (1) permisos y RLS, (2) columna 'segmento' de la serie,
-- (3) índices IPC del DANE. Todo idempotente; se puede repetir sin daño.
-- Córrelo ANTES de subir el código nuevo a GitHub/Render.
-- =====================================================================

-- ============ 1) PERMISOS Y POLÍTICAS RLS ============
-- =====================================================================
-- REPARA TODOS LOS PERMISOS Y POLÍTICAS RLS EN SUPABASE
-- Reaplica GRANTs a app_user, habilita RLS y recrea las políticas de
-- todas las tablas (extraído de las migraciones 001–017). Idempotente.
-- Ejecutar en Supabase -> SQL Editor como 'postgres'.
-- =====================================================================

-- Red de seguridad: acceso de app_user a todo el esquema (cubre el 500 por permiso faltante).
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;


-- ---------- 002_rls.sql ----------
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER TABLE empresa              ENABLE ROW LEVEL SECURITY;
ALTER TABLE resultado_componente ENABLE ROW LEVEL SECURITY;
ALTER TABLE carga_mensual        ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario              ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario_empresa      ENABLE ROW LEVEL SECURITY;
ALTER TABLE segmento             ENABLE ROW LEVEL SECURITY;
ALTER TABLE rol                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria            ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS empresa_sel ON empresa;
DROP POLICY IF EXISTS empresa_mod ON empresa;
CREATE POLICY empresa_sel ON empresa FOR SELECT
  USING (app_allow_all() OR id = ANY (app_empresa_ids()));
CREATE POLICY empresa_mod ON empresa FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS rc_all ON resultado_componente;
CREATE POLICY rc_all ON resultado_componente FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS cm_all ON carga_mensual;
CREATE POLICY cm_all ON carga_mensual FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS usuario_sel ON usuario;
DROP POLICY IF EXISTS usuario_mod ON usuario;
CREATE POLICY usuario_sel ON usuario FOR SELECT
  USING (app_allow_all() OR id = app_user_id() OR empresa_id = ANY (app_empresa_ids()));
CREATE POLICY usuario_mod ON usuario FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS ue_sel ON usuario_empresa;
DROP POLICY IF EXISTS ue_mod ON usuario_empresa;
CREATE POLICY ue_sel ON usuario_empresa FOR SELECT
  USING (app_allow_all() OR usuario_id = app_user_id());
CREATE POLICY ue_mod ON usuario_empresa FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS seg_sel ON segmento;
DROP POLICY IF EXISTS seg_mod ON segmento;
CREATE POLICY seg_sel ON segmento FOR SELECT USING (true);
CREATE POLICY seg_mod ON segmento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS rol_sel ON rol;
DROP POLICY IF EXISTS rol_mod ON rol;
CREATE POLICY rol_sel ON rol FOR SELECT USING (true);
CREATE POLICY rol_mod ON rol FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS aud_ins ON auditoria;
DROP POLICY IF EXISTS aud_sel ON auditoria;
CREATE POLICY aud_ins ON auditoria FOR INSERT WITH CHECK (true);
CREATE POLICY aud_sel ON auditoria FOR SELECT USING (app_allow_all());
GRANT EXECUTE ON FUNCTION app_authenticate(text) TO app_user;
GRANT EXECUTE ON FUNCTION app_scope(int) TO app_user;

-- ---------- 003_hardening.sql ----------
GRANT EXECUTE ON FUNCTION app_authenticate(text) TO app_user;
GRANT EXECUTE ON FUNCTION app_registrar_intento(text, boolean, int, int) TO app_user;
GRANT EXECUTE ON FUNCTION app_set_password(text) TO app_user;
GRANT EXECUTE ON FUNCTION app_set_mfa(text, boolean) TO app_user;

-- ---------- 004_operacion.sql ----------
ALTER TABLE indice_ipc     ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarifa_vigente ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ipc_sel ON indice_ipc;
DROP POLICY IF EXISTS ipc_mod ON indice_ipc;
CREATE POLICY ipc_sel ON indice_ipc FOR SELECT USING (true);
CREATE POLICY ipc_mod ON indice_ipc FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS tv_all ON tarifa_vigente;
CREATE POLICY tv_all ON tarifa_vigente FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON indice_ipc, tarifa_vigente TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tarifa_vigente_id_seq TO app_user;

-- ---------- 005_cargue.sql ----------
ALTER TABLE carga_mensual_detalle ENABLE ROW LEVEL SECURITY;
ALTER TABLE factor_subsidio       ENABLE ROW LEVEL SECURITY;
ALTER TABLE indicador_mensual     ENABLE ROW LEVEL SECURITY;
ALTER TABLE factura_clase         ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cmd_all ON carga_mensual_detalle;
CREATE POLICY cmd_all ON carga_mensual_detalle FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS fs_all ON factor_subsidio;
CREATE POLICY fs_all ON factor_subsidio FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS im_all ON indicador_mensual;
CREATE POLICY im_all ON indicador_mensual FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS fc_all ON factura_clase;
CREATE POLICY fc_all ON factura_clase FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE
  ON carga_mensual_detalle, factor_subsidio, indicador_mensual, factura_clase TO app_user;
GRANT USAGE, SELECT ON SEQUENCE
  carga_mensual_detalle_id_seq, factor_subsidio_id_seq,
  indicador_mensual_id_seq, factura_clase_id_seq TO app_user;

-- ---------- 006_recalculo.sql ----------
ALTER TABLE base_calculo             ENABLE ROW LEVEL SECURITY;
ALTER TABLE macromedicion            ENABLE ROW LEVEL SECURITY;
ALTER TABLE numerador_mensual        ENABLE ROW LEVEL SECURITY;
ALTER TABLE costo_referencia_mensual ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bc_all ON base_calculo;
CREATE POLICY bc_all ON base_calculo FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS mm_all ON macromedicion;
CREATE POLICY mm_all ON macromedicion FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS num_all ON numerador_mensual;
CREATE POLICY num_all ON numerador_mensual FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS crm_all ON costo_referencia_mensual;
CREATE POLICY crm_all ON costo_referencia_mensual FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE
  ON base_calculo, macromedicion, numerador_mensual, costo_referencia_mensual TO app_user;
GRANT USAGE, SELECT ON SEQUENCE
  base_calculo_id_seq, macromedicion_id_seq,
  numerador_mensual_id_seq, costo_referencia_mensual_id_seq TO app_user;

-- ---------- 007_inversiones.sql ----------
ALTER TABLE proyecto_inversion ENABLE ROW LEVEL SECURITY;
ALTER TABLE avance_inversion   ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pi_all ON proyecto_inversion;
CREATE POLICY pi_all ON proyecto_inversion FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS ai_all ON avance_inversion;
CREATE POLICY ai_all ON avance_inversion FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_inversion, avance_inversion TO app_user;
GRANT USAGE, SELECT ON SEQUENCE proyecto_inversion_id_seq, avance_inversion_id_seq TO app_user;

-- ---------- 008_periodos.sql ----------
ALTER TABLE ano_tarifario ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS at_sel ON ano_tarifario;
DROP POLICY IF EXISTS at_mod ON ano_tarifario;
CREATE POLICY at_sel ON ano_tarifario FOR SELECT USING (true);
CREATE POLICY at_mod ON ano_tarifario FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
GRANT SELECT, INSERT, UPDATE, DELETE ON ano_tarifario TO app_user;

-- ---------- 010_territorio.sql ----------
ALTER TABLE departamento      ENABLE ROW LEVEL SECURITY;
ALTER TABLE municipio         ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresa_municipio ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dpto_sel ON departamento;
DROP POLICY IF EXISTS dpto_mod ON departamento;
CREATE POLICY dpto_sel ON departamento FOR SELECT USING (true);
CREATE POLICY dpto_mod ON departamento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS mun_sel ON municipio;
DROP POLICY IF EXISTS mun_mod ON municipio;
CREATE POLICY mun_sel ON municipio FOR SELECT USING (true);
CREATE POLICY mun_mod ON municipio FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS em_all ON empresa_municipio;
CREATE POLICY em_all ON empresa_municipio FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON departamento, municipio, empresa_municipio TO app_user;

-- ---------- 012_aps.sql ----------
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

-- ---------- 013_cargue_bcr.sql ----------
ALTER TABLE costo_particular ENABLE ROW LEVEL SECURITY;
ALTER TABLE bcr_activo       ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cpart_all ON costo_particular;
CREATE POLICY cpart_all ON costo_particular FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS bcr_all ON bcr_activo;
CREATE POLICY bcr_all ON bcr_activo FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON costo_particular, bcr_activo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE costo_particular_id_seq, bcr_activo_id_seq TO app_user;

-- ---------- 014_bcr0_inicio.sql ----------
ALTER TABLE bcr_param ENABLE ROW LEVEL SECURITY;
ALTER TABLE bcr_serie ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bcrparam_all ON bcr_param;
CREATE POLICY bcrparam_all ON bcr_param FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS bcrserie_all ON bcr_serie;
CREATE POLICY bcrserie_all ON bcr_serie FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON bcr_param, bcr_serie TO app_user;

-- ---------- 015_poir_cmi.sql ----------
ALTER TABLE poir_modificacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE activo_cmi        ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poirmod_all ON poir_modificacion;
CREATE POLICY poirmod_all ON poir_modificacion FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
DROP POLICY IF EXISTS acmi_all ON activo_cmi;
CREATE POLICY acmi_all ON activo_cmi FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON poir_modificacion, activo_cmi TO app_user;

-- ---------- 017_ccp_fap.sql ----------
ALTER TABLE ccp_fap ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ccpfap_all ON ccp_fap;
CREATE POLICY ccpfap_all ON ccp_fap FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON ccp_fap TO app_user;

-- Diagnóstico:
SELECT count(*) AS tablas FROM information_schema.tables WHERE table_schema='public';

-- ============ 2) COLUMNA 'segmento' EN LA SERIE 688 ============
-- =====================================================================
--  018_bcr_serie_segmento.sql — segmento histórico en la serie de agua
--  facturada de la 688.
--
--  El paso 1 de la Base de Capital Regulado captura, por año de aplicación
--  de la 688 y por servicio, el agua facturada (Q), el CMI cobrado y el
--  SEGMENTO al que pertenecía la empresa ese año (pudo cambiar en el tiempo).
--  Idempotente.
-- =====================================================================
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS segmento smallint;

-- ============ 3) ÍNDICES IPC DEL DANE ============
-- IPC del DANE (total y sin alimentos ni regulados). Fuente: anexos DANE ago-2026.
-- Idempotente. Ejecutar en Supabase -> SQL Editor.
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,1,50.42,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,2,50.98,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,3,51.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,4,52.1,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,5,52.36,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,6,52.33,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,7,52.26,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,8,52.42,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,9,52.53,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,10,52.56,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,11,52.75,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2003,12,53.07,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,1,53.54,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,2,54.18,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,3,54.71,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,4,54.96,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,5,55.17,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,6,55.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,7,55.49,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,8,55.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,9,55.67,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,10,55.66,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,11,55.82,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2004,12,55.99,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,1,56.45,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,2,57.02,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,3,57.46,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,4,57.72,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,5,57.95,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,6,58.18,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,7,58.21,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,8,58.21,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,9,58.46,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,10,58.6,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,11,58.66,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2005,12,58.7,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,1,59.02,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,2,59.41,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,3,59.83,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,4,60.09,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,5,60.29,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,6,60.48,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,7,60.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,8,60.96,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,9,61.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,10,61.05,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,11,61.19,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2006,12,61.33,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,1,61.8,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,2,62.53,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,3,63.29,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,4,63.85,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,5,64.05,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,6,64.12,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,7,64.23,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,8,64.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,9,64.2,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,10,64.2,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,11,64.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2007,12,64.82,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,1,65.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,2,66.5,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,3,67.04,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,4,67.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,5,68.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,6,68.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,7,69.06,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,8,69.19,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,9,69.06,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,10,69.3,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,11,69.49,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2008,12,69.8,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,1,70.21,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,2,70.8,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,3,71.15,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,4,71.38,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,5,71.39,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,6,71.35,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,7,71.32,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,8,71.35,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,9,71.28,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,10,71.19,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,11,71.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2009,12,71.2,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,1,71.69,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,2,72.28,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,3,72.46,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,4,72.79,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,5,72.87,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,6,72.95,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,7,72.92,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,8,73.0,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,9,72.9,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,10,72.84,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,11,72.98,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2010,12,73.45,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,1,74.12,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,2,74.57,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,3,74.77,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,4,74.86,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,5,75.07,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,6,75.31,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,7,75.42,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,8,75.39,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,9,75.62,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,10,75.77,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,11,75.87,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2011,12,76.19,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,1,76.75,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,2,77.22,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,3,77.31,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,4,77.42,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,5,77.66,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,6,77.72,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,7,77.7,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,8,77.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,9,77.96,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,10,78.08,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,11,77.98,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2012,12,78.05,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,1,78.28,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,2,78.63,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,3,78.79,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,4,78.99,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,5,79.21,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,6,79.39,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,7,79.43,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,8,79.5,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,9,79.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,10,79.52,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,11,79.35,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2013,12,79.56,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,1,79.95,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,2,80.45,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,3,80.77,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,4,81.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,5,81.53,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,6,81.61,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,7,81.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,8,81.9,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,9,82.01,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,10,82.14,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,11,82.25,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2014,12,82.47,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,1,83.0,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,2,83.96,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,3,84.45,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,4,84.9,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,5,85.12,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,6,85.21,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,7,85.37,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,8,85.78,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,9,86.39,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,10,86.98,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,11,87.51,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2015,12,88.05,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,1,89.19,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,2,90.33,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,3,91.18,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,4,91.63,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,5,92.1,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,6,92.54,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,7,93.02,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,8,92.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,9,92.68,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,10,92.62,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,11,92.73,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2016,12,93.11,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,1,94.07,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,2,95.01,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,3,95.46,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,4,95.91,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,5,96.12,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,6,96.23,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,7,96.18,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,8,96.32,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,9,96.36,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,10,96.37,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,11,96.55,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2017,12,96.92,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,1,97.53,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,2,98.22,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,3,98.45,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,4,98.91,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,5,99.16,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,6,99.31,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,7,99.18,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,8,99.3,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,9,99.47,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,10,99.59,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,11,99.7,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2018,12,100.0,NULL,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,1,100.6,100.42,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,2,101.18,100.93,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,3,101.62,101.14,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,4,102.12,101.53,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,5,102.44,101.76,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,6,102.71,102.02,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,7,102.94,102.14,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,8,103.03,102.3,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,9,103.26,102.42,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,10,103.43,102.53,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,11,103.54,102.7,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2019,12,103.8,103.1,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,1,104.24,103.48,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,2,104.94,103.96,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,3,105.53,104.17,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,4,105.7,104.07,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,5,105.36,103.82,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,6,104.97,103.7,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,7,104.97,103.83,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,8,104.96,103.91,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,9,105.29,104.13,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,10,105.23,104.12,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,11,105.08,103.86,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2020,12,105.48,104.25,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,1,105.91,104.38,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,2,106.58,104.95,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,3,107.12,105.14,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,4,107.76,105.37,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,5,108.84,105.44,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,6,108.78,105.64,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,7,109.14,105.96,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,8,109.62,106.31,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,9,110.04,106.5,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,10,110.06,106.22,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,11,110.6,106.5,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2021,12,111.41,106.84,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,1,113.26,108.0,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,2,115.11,109.26,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,3,116.26,109.89,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,4,117.71,110.9,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,5,118.7,111.63,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,6,119.31,112.04,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,7,120.27,112.78,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,8,121.5,113.64,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,9,122.63,114.47,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,10,123.51,115.12,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,11,124.46,115.89,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2022,12,126.03,117.01,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,1,128.27,118.55,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,2,130.4,120.23,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,3,131.77,121.44,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,4,132.8,122.53,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,5,133.38,123.32,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,6,133.78,123.82,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,7,134.45,124.31,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,8,135.39,124.92,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,9,136.11,125.36,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,10,136.45,125.71,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,11,137.09,126.16,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2023,12,137.72,126.87,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,1,138.98,127.82,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,2,140.49,128.97,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,3,141.48,129.65,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,4,142.32,130.33,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,5,142.92,130.87,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,6,143.38,131.26,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,7,143.67,131.53,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,8,143.67,131.8,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,9,144.02,132.24,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,10,143.83,132.43,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,11,144.22,132.92,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2024,12,144.88,133.4,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,1,146.24,134.24,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,2,147.9,135.28,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,3,148.68,135.93,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,4,149.66,136.71,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,5,150.14,137.12,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,6,150.3,137.52,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,7,150.71,137.83,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,8,150.99,138.15,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,9,151.48,138.63,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,10,151.76,139.04,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,11,151.87,139.38,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2025,12,152.27,140.09,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,1,154.07,141.47,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,2,155.73,142.75,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,3,156.94,143.8,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,4,158.17,144.62,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,5,158.91,145.32,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,6,159.53,145.78,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,7,159.79,146.05,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);
INSERT INTO indice_ipc(anio,mes,indice,ipcs,fuente,procedencia) VALUES (2026,8,160.42,146.61,'DANE','reportada') ON CONFLICT (anio,mes) DO UPDATE SET indice=COALESCE(excluded.indice,indice_ipc.indice), ipcs=COALESCE(excluded.ipcs,indice_ipc.ipcs);

-- ============ Verificación final ============
SELECT (SELECT count(*) FROM municipio) AS municipios,
       (SELECT count(*) FROM segmento) AS segmentos,
       (SELECT count(*) FROM information_schema.columns WHERE table_name='bcr_serie' AND column_name='segmento') AS col_segmento,
       (SELECT indice FROM indice_ipc WHERE anio=2014 AND mes=12) AS ipc_dic_2014,
       (SELECT indice FROM indice_ipc WHERE anio=2025 AND mes=12) AS ipc_dic_2025;
