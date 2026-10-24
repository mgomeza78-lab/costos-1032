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
