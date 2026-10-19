-- =====================================================================
--  003_hardening.sql — endurecimiento de la autenticación.
--  Columnas de seguridad en usuario, autenticación ampliada, bloqueo de
--  intentos y auto-servicio (contraseña / MFA) atado al usuario autenticado.
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

ALTER TABLE usuario ADD COLUMN IF NOT EXISTS intentos_fallidos  int         NOT NULL DEFAULT 0;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS bloqueado_hasta     timestamptz;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS mfa_secret          text;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS mfa_activo          boolean     NOT NULL DEFAULT false;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS debe_cambiar_pass   boolean     NOT NULL DEFAULT false;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS ultimo_login        timestamptz;

-- ---------- Autenticación ampliada (SECURITY DEFINER; no depende de RLS) ----------
DROP FUNCTION IF EXISTS app_authenticate(text);
CREATE OR REPLACE FUNCTION app_authenticate(p_email text)
RETURNS TABLE(id int, nombre text, email text, password_hash text, rol_codigo text,
              empresa_id int, activo boolean, mfa_activo boolean, mfa_secret text,
              bloqueado_hasta timestamptz, debe_cambiar_pass boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$
  SELECT u.id, u.nombre, u.email, u.password_hash, r.codigo, u.empresa_id, u.activo,
         u.mfa_activo, u.mfa_secret, u.bloqueado_hasta, u.debe_cambiar_pass
  FROM usuario u JOIN rol r ON r.id = u.rol_id
  WHERE lower(u.email) = lower(p_email)
$$;
REVOKE ALL ON FUNCTION app_authenticate(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_authenticate(text) TO app_user;

-- ---------- Registro de intentos y bloqueo temporal ----------
CREATE OR REPLACE FUNCTION app_registrar_intento(p_email text, p_exito boolean,
                                                 p_max int, p_lock_min int)
RETURNS TABLE(bloqueado boolean, bloqueado_hasta timestamptz, intentos int)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS
$$
DECLARE v_id int; v_int int; v_lock timestamptz;
BEGIN
  SELECT u.id, u.intentos_fallidos INTO v_id, v_int FROM usuario u
  WHERE lower(u.email) = lower(p_email);
  IF v_id IS NULL THEN
    RETURN QUERY SELECT false, NULL::timestamptz, 0;   -- no revela si el correo existe
    RETURN;
  END IF;
  IF p_exito THEN
    UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_login = now()
    WHERE id = v_id;
    RETURN QUERY SELECT false, NULL::timestamptz, 0;
    RETURN;
  END IF;
  v_int := COALESCE(v_int, 0) + 1;
  IF v_int >= p_max THEN
    v_lock := now() + make_interval(mins => p_lock_min);
    UPDATE usuario SET intentos_fallidos = v_int, bloqueado_hasta = v_lock WHERE id = v_id;
    RETURN QUERY SELECT true, v_lock, v_int;
  ELSE
    UPDATE usuario SET intentos_fallidos = v_int WHERE id = v_id;
    RETURN QUERY SELECT false, NULL::timestamptz, v_int;
  END IF;
END
$$;
REVOKE ALL ON FUNCTION app_registrar_intento(text, boolean, int, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_registrar_intento(text, boolean, int, int) TO app_user;

-- ---------- Auto-servicio atado al usuario autenticado (app.user_id) ----------
--  Solo pueden afectar al propio usuario de la sesión; no reciben el id como parámetro.
CREATE OR REPLACE FUNCTION app_set_password(p_hash text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$
  UPDATE usuario SET password_hash = p_hash, debe_cambiar_pass = false
  WHERE id = nullif(current_setting('app.user_id', true), '')::int
$$;
REVOKE ALL ON FUNCTION app_set_password(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_set_password(text) TO app_user;

CREATE OR REPLACE FUNCTION app_set_mfa(p_secret text, p_activo boolean) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public AS
$$
  UPDATE usuario SET mfa_secret = p_secret, mfa_activo = p_activo
  WHERE id = nullif(current_setting('app.user_id', true), '')::int
$$;
REVOKE ALL ON FUNCTION app_set_mfa(text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_set_mfa(text, boolean) TO app_user;

-- ---------- (Producción) fijar contraseña del rol de aplicación ----------
--  La autenticación por 'trust' sirve solo en desarrollo local. En producción:
--     ALTER ROLE app_user WITH PASSWORD '***';   -- y use DB_APP_PASSWORD
--  junto con pg_hba.conf en 'scram-sha-256'.
