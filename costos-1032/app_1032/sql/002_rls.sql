-- =====================================================================
--  002_rls.sql — rol de aplicación, Row-Level Security y funciones de acceso.
--  Se ejecuta como el rol dueño (postgres). El aislamiento por empresa NO
--  depende de que la consulta "recuerde" filtrar: lo impone la base.
-- =====================================================================

-- ---------- Rol de aplicación: NO superusuario, NO bypass RLS, NO dueño ----------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- ---------- Contexto de sesión (lo fija la aplicación por petición) ----------
--  app.allow_all  = 'on'  -> acceso irrestricto (Administrador / Analista-todas)
--  app.empresa_ids = CSV  -> empresas permitidas (Empresa/Auditor/Analista-subconjunto)
--  app.user_id     = id del usuario autenticado
CREATE OR REPLACE FUNCTION app_allow_all() RETURNS boolean
  LANGUAGE sql STABLE AS
$$ SELECT coalesce(current_setting('app.allow_all', true), 'off') = 'on' $$;

CREATE OR REPLACE FUNCTION app_empresa_ids() RETURNS integer[]
  LANGUAGE sql STABLE AS
$$ SELECT string_to_array(coalesce(nullif(current_setting('app.empresa_ids', true), ''), '0'), ',')::int[] $$;

CREATE OR REPLACE FUNCTION app_user_id() RETURNS integer
  LANGUAGE sql STABLE AS
$$ SELECT coalesce(nullif(current_setting('app.user_id', true), ''), '0')::int $$;

-- ---------- Activar RLS ----------
ALTER TABLE empresa              ENABLE ROW LEVEL SECURITY;
ALTER TABLE resultado_componente ENABLE ROW LEVEL SECURITY;
ALTER TABLE carga_mensual        ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario              ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario_empresa      ENABLE ROW LEVEL SECURITY;
ALTER TABLE segmento             ENABLE ROW LEVEL SECURITY;
ALTER TABLE rol                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria            ENABLE ROW LEVEL SECURITY;

-- ---------- empresa: ve la suya (o todas si admin); solo admin crea/edita ----------
DROP POLICY IF EXISTS empresa_sel ON empresa;
DROP POLICY IF EXISTS empresa_mod ON empresa;
CREATE POLICY empresa_sel ON empresa FOR SELECT
  USING (app_allow_all() OR id = ANY (app_empresa_ids()));
CREATE POLICY empresa_mod ON empresa FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());

-- ---------- resultado_componente: por empresa permitida ----------
DROP POLICY IF EXISTS rc_all ON resultado_componente;
CREATE POLICY rc_all ON resultado_componente FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- carga_mensual: la empresa carga y ve lo suyo ----------
DROP POLICY IF EXISTS cm_all ON carga_mensual;
CREATE POLICY cm_all ON carga_mensual FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- usuario: cada quien se ve a sí mismo y a los de su empresa; solo admin crea ----------
DROP POLICY IF EXISTS usuario_sel ON usuario;
DROP POLICY IF EXISTS usuario_mod ON usuario;
CREATE POLICY usuario_sel ON usuario FOR SELECT
  USING (app_allow_all() OR id = app_user_id() OR empresa_id = ANY (app_empresa_ids()));
CREATE POLICY usuario_mod ON usuario FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());

-- ---------- usuario_empresa: el usuario ve sus asignaciones; solo admin administra ----------
DROP POLICY IF EXISTS ue_sel ON usuario_empresa;
DROP POLICY IF EXISTS ue_mod ON usuario_empresa;
CREATE POLICY ue_sel ON usuario_empresa FOR SELECT
  USING (app_allow_all() OR usuario_id = app_user_id());
CREATE POLICY ue_mod ON usuario_empresa FOR ALL
  USING (app_allow_all()) WITH CHECK (app_allow_all());

-- ---------- catálogo normativo: lo lee cualquiera autenticado; solo admin escribe ----------
DROP POLICY IF EXISTS seg_sel ON segmento;  DROP POLICY IF EXISTS seg_mod ON segmento;
CREATE POLICY seg_sel ON segmento FOR SELECT USING (true);
CREATE POLICY seg_mod ON segmento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS rol_sel ON rol;        DROP POLICY IF EXISTS rol_mod ON rol;
CREATE POLICY rol_sel ON rol FOR SELECT USING (true);
CREATE POLICY rol_mod ON rol FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

-- ---------- auditoría: cualquiera anota; solo admin lee; nadie modifica/borra ----------
DROP POLICY IF EXISTS aud_ins ON auditoria;  DROP POLICY IF EXISTS aud_sel ON auditoria;
CREATE POLICY aud_ins ON auditoria FOR INSERT WITH CHECK (true);
CREATE POLICY aud_sel ON auditoria FOR SELECT USING (app_allow_all());

-- =====================================================================
--  Funciones SECURITY DEFINER para el arranque de la sesión (login).
--  Corren con privilegios del dueño (bypassan RLS) y exponen SOLO lo justo.
-- =====================================================================

-- Autenticación: datos mínimos del usuario por correo.
CREATE OR REPLACE FUNCTION app_authenticate(p_email text)
RETURNS TABLE(id int, nombre text, email text, password_hash text,
              rol_codigo text, empresa_id int, activo boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$
  SELECT u.id, u.nombre, u.email, u.password_hash, r.codigo, u.empresa_id, u.activo
  FROM usuario u JOIN rol r ON r.id = u.rol_id
  WHERE lower(u.email) = lower(p_email)
$$;
REVOKE ALL ON FUNCTION app_authenticate(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_authenticate(text) TO app_user;

-- Alcance del usuario: (allow_all, empresa_ids) según su rol y asignaciones.
CREATE OR REPLACE FUNCTION app_scope(p_user_id int)
RETURNS TABLE(allow_all boolean, empresa_ids int[])
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS
$$
DECLARE rc text; eid int;
BEGIN
  SELECT r.codigo, u.empresa_id INTO rc, eid
  FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = p_user_id;
  IF rc = 'admin' THEN
    RETURN QUERY SELECT true, ARRAY[]::int[];
  ELSIF rc = 'analista' THEN
    IF EXISTS (SELECT 1 FROM usuario_empresa WHERE usuario_id = p_user_id) THEN
      RETURN QUERY SELECT false, (SELECT array_agg(empresa_id) FROM usuario_empresa WHERE usuario_id = p_user_id);
    ELSE
      RETURN QUERY SELECT true, ARRAY[]::int[];   -- analista sin asignación explícita: todas
    END IF;
  ELSE  -- empresa, auditor
    RETURN QUERY SELECT false, CASE WHEN eid IS NULL THEN ARRAY[]::int[] ELSE ARRAY[eid] END;
  END IF;
END
$$;
REVOKE ALL ON FUNCTION app_scope(int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_scope(int) TO app_user;
