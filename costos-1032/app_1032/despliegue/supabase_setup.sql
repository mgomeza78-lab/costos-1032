-- =====================================================================
-- supabase_setup.sql — ESTRUCTURA de la plataforma de costos CRA 1032
-- Péguelo y ejecútelo en el EDITOR SQL de Supabase (una sola vez).
-- Crea tablas, Row-Level Security, funciones y el catálogo de años tarifarios.
-- Al final fija la contraseña del rol de aplicación 'app_user':
--   REEMPLACE 'CAMBIA_ESTA_CLAVE_app' por una clave suya y úsela en DB_APP_PASSWORD.
-- =====================================================================

-- ---------- 001_schema.sql ----------
-- =====================================================================
--  Estudios de costos CRA 1032/2026 — esquema multiempresa (tenant)
--  001_schema.sql — tablas. Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- ---------- Catálogo normativo (común; de solo lectura para no-admin) ----------
CREATE TABLE IF NOT EXISTS segmento (
  id            smallint PRIMARY KEY,
  nombre        text NOT NULL,
  susc_min      integer,
  susc_max      integer,
  r             numeric(6,5) NOT NULL,   -- tasa de remuneración del capital (art. 2.1.2.1.3.1.7)
  kct           numeric(6,5) NOT NULL,   -- tasa de capital de trabajo       (art. 2.1.2.1.3.1.8)
  ipuf_estrella numeric(6,2),
  articulo_r    text,
  articulo_kct  text
);

CREATE TABLE IF NOT EXISTS rol (
  id     smallint PRIMARY KEY,
  codigo text UNIQUE NOT NULL,          -- admin | analista | empresa | auditor
  nombre text NOT NULL
);

-- ---------- Empresas (tenants) ----------
CREATE TABLE IF NOT EXISTS empresa (
  id            serial PRIMARY KEY,
  codigo        text UNIQUE NOT NULL,          -- LAS_CEIBAS, ESSMAR, AMB...
  nombre        text NOT NULL,
  nit           text,
  municipio     text,
  segmento_id   smallint REFERENCES segmento(id),
  presta_ac     boolean NOT NULL DEFAULT false,
  presta_al     boolean NOT NULL DEFAULT false,
  esquema       text,
  r             numeric(6,5),
  kct           numeric(6,5),
  fecha_inicio_688       date,
  fecha_inicio_1032      date,
  aplicacion_1032_tardia boolean NOT NULL DEFAULT false,
  creado_en     timestamptz NOT NULL DEFAULT now()
);

-- ---------- Usuarios ----------
CREATE TABLE IF NOT EXISTS usuario (
  id            serial PRIMARY KEY,
  email         text UNIQUE NOT NULL,
  nombre        text NOT NULL,
  password_hash text NOT NULL,
  rol_id        smallint NOT NULL REFERENCES rol(id),
  empresa_id    integer REFERENCES empresa(id),  -- solo para rol empresa/auditor
  activo        boolean NOT NULL DEFAULT true,
  creado_en     timestamptz NOT NULL DEFAULT now()
);

-- ---------- Asignación de analistas a empresas (subconjunto) ----------
CREATE TABLE IF NOT EXISTS usuario_empresa (
  usuario_id integer NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
  empresa_id integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  PRIMARY KEY (usuario_id, empresa_id)
);

-- ---------- Resultados: costos económicos de referencia (período de inicio) ----------
CREATE TABLE IF NOT EXISTS resultado_componente (
  id           serial PRIMARY KEY,
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio     text NOT NULL,       -- acueducto | alcantarillado | —
  componente   text NOT NULL,       -- CMA | CMO | CMI | CMICT | CARGO_FIJO | CARGO_CONSUMO | BCR0 ...
  valor        double precision,
  unidad       text,
  procedencia  text,                -- normativa | validada | radicada | SUI | supuesto
  fuente       text,
  articulo     text,                -- artículo de la Res. 1032 que lo fundamenta
  calculado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, servicio, componente)
);

-- ---------- Carga mensual (gancho para la capa de operación mensual) ----------
CREATE TABLE IF NOT EXISTS carga_mensual (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  mes           smallint NOT NULL,
  servicio      text,
  suscriptores  integer,
  m3_facturados double precision,
  origen        text,              -- SUI | archivo_propio
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);

-- ---------- Auditoría (append-only) ----------
CREATE TABLE IF NOT EXISTS auditoria (
  id         bigserial PRIMARY KEY,
  usuario_id integer,
  email      text,
  accion     text NOT NULL,
  objeto     text,
  empresa_id integer,
  detalle    text,
  en         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_rc_empresa   ON resultado_componente(empresa_id);
CREATE INDEX IF NOT EXISTS ix_cm_empresa   ON carga_mensual(empresa_id);
CREATE INDEX IF NOT EXISTS ix_usuario_emp  ON usuario(empresa_id);

-- ---------- 002_rls.sql ----------
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

-- ---------- 003_hardening.sql ----------
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

-- ---------- 004_operacion.sql ----------
-- =====================================================================
--  004_operacion.sql — capa de operación mensual.
--  Índice IPC (referencia nacional cargada), carga mensual ampliada y
--  tarifa vigente por empresa/mes/servicio (resultado del motor de gatillo).
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- ---------- Índice IPC mensual (referencia nacional; DATO CARGADO, no inventado) ----------
CREATE TABLE IF NOT EXISTS indice_ipc (
  anio        smallint NOT NULL,
  mes         smallint NOT NULL,
  indice      numeric(14,6) NOT NULL,       -- número índice IPC (base DANE)
  fuente      text,
  procedencia text DEFAULT 'SUI/DANE',      -- normativa | reportada | SUI | supuesto
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (anio, mes)
);

-- ---------- Ampliar la carga mensual ----------
ALTER TABLE carga_mensual ADD COLUMN IF NOT EXISTS facturacion double precision;
ALTER TABLE carga_mensual ADD COLUMN IF NOT EXISTS novedades   text;

-- ---------- Tarifa vigente mensual (salida del motor de indexación) ----------
CREATE TABLE IF NOT EXISTS tarifa_vigente (
  id               serial PRIMARY KEY,
  empresa_id       integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio             smallint NOT NULL,
  mes              smallint NOT NULL,
  servicio         text NOT NULL,
  cargo_fijo       double precision,
  cargo_consumo    double precision,
  factor_acumulado double precision,        -- respecto a la base del período de inicio
  variacion_acum   double precision,        -- variación IPC acumulada desde la última indexación
  indexado         boolean NOT NULL DEFAULT false,   -- el gatillo disparó este mes
  calculado_en     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);
CREATE INDEX IF NOT EXISTS ix_tv_empresa ON tarifa_vigente(empresa_id);

-- ---------- RLS ----------
ALTER TABLE indice_ipc     ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarifa_vigente ENABLE ROW LEVEL SECURITY;

-- IPC: lo lee cualquiera autenticado; lo escribe admin / analista-todas (allow_all)
DROP POLICY IF EXISTS ipc_sel ON indice_ipc;  DROP POLICY IF EXISTS ipc_mod ON indice_ipc;
CREATE POLICY ipc_sel ON indice_ipc FOR SELECT USING (true);
CREATE POLICY ipc_mod ON indice_ipc FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

-- tarifa_vigente: por empresa permitida
DROP POLICY IF EXISTS tv_all ON tarifa_vigente;
CREATE POLICY tv_all ON tarifa_vigente FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants para las tablas nuevas (los GRANT previos no las cubren) ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON indice_ipc, tarifa_vigente TO app_user;
GRANT USAGE, SELECT ON SEQUENCE tarifa_vigente_id_seq TO app_user;

-- ---------- 005_cargue.sql ----------
-- =====================================================================
--  005_cargue.sql — cargue mensual por clase, factores, indicadores,
--  factura teórica por estrato (derivada) y segunda canasta de indexación.
--  Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- IPCs (índice de precios específicos) para CMA/CMO/CMICT; indice (IPC) ya existe (CMI).
ALTER TABLE indice_ipc ADD COLUMN IF NOT EXISTS ipcs numeric(14,6);

-- Segunda canasta en la tarifa vigente: variación/indexación por IPC (CMI).
ALTER TABLE tarifa_vigente ADD COLUMN IF NOT EXISTS var_ipc      double precision;
ALTER TABLE tarifa_vigente ADD COLUMN IF NOT EXISTS indexado_ipc boolean NOT NULL DEFAULT false;

-- ---------- Detalle comercial por clase (formulario SUI 6080/6081) ----------
CREATE TABLE IF NOT EXISTS carga_mensual_detalle (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio           smallint NOT NULL,
  mes            smallint NOT NULL,
  servicio       text NOT NULL,            -- AC | AL (o acueducto/alcantarillado)
  clase          smallint NOT NULL,        -- clase de uso SUI (1-6 estratos; 10-13 no residencial)
  suscriptores   integer,
  m3             double precision,
  m3_subsidiable double precision,
  origen         text,                     -- SUI | archivo_propio | muestra
  cargado_por    integer REFERENCES usuario(id),
  cargado_en     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, clase)
);

-- ---------- Factores de subsidio/contribución por clase (SUI 1051/1114) ----------
CREATE TABLE IF NOT EXISTS factor_subsidio (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  vigencia        smallint NOT NULL,
  servicio        text NOT NULL,
  clase           smallint NOT NULL,
  factor_cargofijo double precision,       -- subsidio (-) / contribución (+)
  factor_consumo   double precision,
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, vigencia, servicio, clase)
);

-- ---------- Indicadores mensuales (6084 SURICATA, etc.) ----------
CREATE TABLE IF NOT EXISTS indicador_mensual (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  mes           smallint NOT NULL,
  servicio      text NOT NULL,
  ipuf_real     double precision,
  continuidad_h double precision,
  irca          double precision,
  reclamaciones integer,
  cortes        integer,
  reconexiones  integer,
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);

-- ---------- Factura teórica por clase (DERIVADA) ----------
CREATE TABLE IF NOT EXISTS factura_clase (
  id                    serial PRIMARY KEY,
  empresa_id            integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio                  smallint NOT NULL,
  mes                   smallint NOT NULL,
  servicio              text NOT NULL,
  clase                 smallint NOT NULL,
  suscriptores          integer,
  m3                    double precision,
  m3_subsidiable        double precision,
  cf_facturado          double precision,
  cc_facturado          double precision,
  subsidio_contribucion double precision,
  factura_total         double precision,
  calculado_en          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, clase)
);

CREATE INDEX IF NOT EXISTS ix_cmd_emp ON carga_mensual_detalle(empresa_id);
CREATE INDEX IF NOT EXISTS ix_fac_emp ON factura_clase(empresa_id);

-- ---------- RLS por empresa en las nuevas tablas ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE
  ON carga_mensual_detalle, factor_subsidio, indicador_mensual, factura_clase TO app_user;
GRANT USAGE, SELECT ON SEQUENCE
  carga_mensual_detalle_id_seq, factor_subsidio_id_seq,
  indicador_mensual_id_seq, factura_clase_id_seq TO app_user;

-- ---------- 006_recalculo.sql ----------
-- =====================================================================
--  006_recalculo.sql — motor de recálculo mensual (seguimiento/control).
--  Calcula los costos económicos de referencia DEL MES y ACUMULADOS con los
--  drivers reales del mes (N, CCP, numeradores del balance), aplicando las
--  fórmulas validadas del núcleo. No re-fija la tarifa cobrada (esa es el costo
--  del estudio indexado por el gatillo del 3 %); sirve para monitorear CCP,
--  pérdidas y suficiencia, y para acumular la línea base del recálculo anual
--  (art. 2.1.2.1.1.9). Se ejecuta como el rol dueño (postgres).
-- =====================================================================

-- ---------- Parámetros y numeradores BASE por empresa/servicio (año base) ----------
-- Alimenta el motor con lo estructural/normativo: numeradores del estudio, N, CCP,
-- AF, factores de indexación Fa y kct. Procedencia: validada | radicada | normativa.
CREATE TABLE IF NOT EXISTS base_calculo (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio    text NOT NULL,                 -- acueducto | alcantarillado
  clave       text NOT NULL,                 -- CACe,COCe,CE,CIQ,COIR,ICTA,ITO,TA,N,CCP,AF,Fa_cma,Fa_cmo,Fa_cmict,kct,denom_cmict,CMI_base
  valor       double precision,
  unidad      text,
  articulo    text,
  procedencia text,                          -- validada | radicada | normativa | supuesto
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, servicio, clave)
);

-- ---------- Macromedición: agua producida/suministrada por punto (mensual) ----------
-- Cargue PROPIO (no hay reporte mensual del SUI de producción). El agua en bloque,
-- cuando aplique, se toma del SUI (ACU-C-1002/1003).
CREATE TABLE IF NOT EXISTS macromedicion (
  id                 serial PRIMARY KEY,
  empresa_id         integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio               smallint NOT NULL,
  mes                smallint NOT NULL,
  servicio           text NOT NULL,          -- acueducto (producción) | alcantarillado (vertimiento tratado)
  punto              text NOT NULL,          -- nombre del punto de macromedición
  m3_producido       double precision,       -- agua producida/suministrada por el punto
  m3_bloque_entregado double precision,      -- agua en bloque entregada a otro prestador (ACU-C-1002)
  m3_bloque_recibido  double precision,      -- agua en bloque recibida de otro prestador (ACU-C-1003)
  origen             text DEFAULT 'propio',  -- propio | SUI
  cargado_por        integer REFERENCES usuario(id),
  cargado_en         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, punto)
);

-- ---------- Numeradores de costo DEL MES (del balance de prueba clasificado) ----------
-- Los produce el clasificador (lector_balance + catálogo) sobre el balance del mes.
CREATE TABLE IF NOT EXISTS numerador_mensual (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio        smallint NOT NULL,
  mes         smallint NOT NULL,
  servicio    text NOT NULL,                 -- acueducto | alcantarillado | conjunto
  concepto    text NOT NULL,                 -- CACe,COCe,CE,CIQ,COIR,ICTA,ITO,TA
  valor       double precision,
  origen      text DEFAULT 'balance',        -- balance | prorrateo_base | ajuste
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio, concepto)
);

-- ---------- Resultados: costo de referencia del mes y acumulado ----------
CREATE TABLE IF NOT EXISTS costo_referencia_mensual (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio        smallint NOT NULL,
  mes         smallint NOT NULL,
  servicio    text NOT NULL,
  -- volúmenes y drivers del mes
  n_mes        double precision,             -- suscriptores del mes
  af_mes       double precision,             -- agua facturada del mes (m³)
  ap_mes       double precision,             -- agua producida del mes (m³)
  perdidas_mes double precision,             -- AP - AF (m³)
  ianc         double precision,             -- índice de agua no contabilizada (%)
  ccp_mes      double precision,             -- consumo corregido por pérdidas del mes (m³)
  -- costos de referencia del mes ($/susc·mes cargo fijo; $/m³ los demás)
  cma_mes   double precision, cmo_mes   double precision,
  cmi_mes   double precision, cmict_mes double precision,
  -- costos de referencia acumulados (year-to-date)
  ccp_acum  double precision,
  cma_acum  double precision, cmo_acum  double precision,
  cmi_acum  double precision, cmict_acum double precision,
  -- suficiencia: costo cobrado (indexado) vs costo de referencia del mes
  cobrado_cf    double precision,            -- cargo fijo cobrado (tarifa_vigente)
  cobrado_cc    double precision,            -- cargo consumo cobrado
  ref_cf        double precision,            -- cargo fijo de referencia del mes (= cma_mes)
  ref_cc        double precision,            -- cargo consumo de referencia (= cmo+cmi+cmict del mes)
  brecha_cf     double precision,            -- cobrado - referencia (cargo fijo)
  brecha_cc     double precision,            -- cobrado - referencia (cargo consumo)
  origen_numerador text,                     -- balance | prorrateo_base
  calculado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, mes, servicio)
);

CREATE INDEX IF NOT EXISTS ix_bc_emp  ON base_calculo(empresa_id);
CREATE INDEX IF NOT EXISTS ix_mm_emp  ON macromedicion(empresa_id);
CREATE INDEX IF NOT EXISTS ix_num_emp ON numerador_mensual(empresa_id);
CREATE INDEX IF NOT EXISTS ix_crm_emp ON costo_referencia_mensual(empresa_id);

-- ---------- RLS por empresa ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE
  ON base_calculo, macromedicion, numerador_mensual, costo_referencia_mensual TO app_user;
GRANT USAGE, SELECT ON SEQUENCE
  base_calculo_id_seq, macromedicion_id_seq,
  numerador_mensual_id_seq, costo_referencia_mensual_id_seq TO app_user;

-- ---------- 007_inversiones.sql ----------
-- =====================================================================
--  007_inversiones.sql — módulo de Inversiones / POIR.
--  Registro de proyectos de inversión con los campos de la Res. CRA 1032 y
--  seguimiento del avance físico y financiero por corte hasta la entrada en
--  operación. Cada proyecto se clasifica como asociado al CMI_POIR (opera desde
--  el primer año tarifario, 2027; art. 2.1.2.1.3.5.14) o a reconocer EXPOST con
--  la fórmula general (art. 2.1.2.1.3.5). En el período de inicio solo se registra
--  y hace seguimiento; la base alimenta el primer recálculo. Rol dueño (postgres).
-- =====================================================================

-- ---------- Proyecto de inversión (se crea planeado) ----------
CREATE TABLE IF NOT EXISTS proyecto_inversion (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  codigo_poir   text NOT NULL,                 -- código del proyecto en el POIR
  nombre        text NOT NULL,
  servicio      text NOT NULL,                 -- acueducto | alcantarillado
  aps           text,                          -- área de prestación del servicio
  componente_sistema text,                     -- captación, aducción, conducción, tratamiento,
                                               -- almacenamiento, distribución (ac); recolección,
                                               -- transporte, tratamiento de aguas residuales (al)
  meta_asociada text,                          -- estándar/meta que atiende (cobertura, continuidad,
                                               -- calidad IRCA, pérdidas/IANC…)
  clasificacion text NOT NULL DEFAULT 'CMI_POIR',  -- CMI_POIR | expost_general
  origen        text NOT NULL DEFAULT 'POIR_nuevo', -- POIR_688 | POIR_nuevo
  valor_planeado double precision,             -- presupuesto / valor planeado (VPI)
  fecha_planeada_operacion date,               -- fecha planeada de entrada en operación
  fecha_real_operacion     date,               -- fecha real (cuando entra en operación)
  estado        text NOT NULL DEFAULT 'planeado',  -- planeado | en_ejecucion | en_operacion | suspendido
  via688        double precision,              -- valor del índice de inversión acumulado 688 (si POIR_688)
  vp_recaudo    double precision,              -- valor presente del recaudo asociado (688)
  vida_util     numeric(6,2),                  -- años (para el CMI_POIR del recálculo)
  observacion   text,
  creado_por    integer REFERENCES usuario(id),
  creado_en     timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, codigo_poir),
  CHECK (clasificacion IN ('CMI_POIR','expost_general')),
  CHECK (estado IN ('planeado','en_ejecucion','en_operacion','suspendido'))
);

-- ---------- Avance físico y financiero por corte ----------
CREATE TABLE IF NOT EXISTS avance_inversion (
  id            serial PRIMARY KEY,
  empresa_id    integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  proyecto_id   integer NOT NULL REFERENCES proyecto_inversion(id) ON DELETE CASCADE,
  anio          smallint NOT NULL,
  mes           smallint NOT NULL,
  avance_fisico double precision,              -- % acumulado (0..100)
  avance_financiero double precision,          -- valor ejecutado ACUMULADO ($)
  observacion   text,
  cargado_por   integer REFERENCES usuario(id),
  cargado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, proyecto_id, anio, mes),
  CHECK (avance_fisico IS NULL OR (avance_fisico >= 0 AND avance_fisico <= 100))
);

CREATE INDEX IF NOT EXISTS ix_pi_emp ON proyecto_inversion(empresa_id);
CREATE INDEX IF NOT EXISTS ix_ai_emp ON avance_inversion(empresa_id);
CREATE INDEX IF NOT EXISTS ix_ai_proy ON avance_inversion(proyecto_id);

-- ---------- RLS por empresa ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_inversion, avance_inversion TO app_user;
GRANT USAGE, SELECT ON SEQUENCE proyecto_inversion_id_seq, avance_inversion_id_seq TO app_user;

-- ---------- 008_periodos.sql ----------
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

-- ---------- Contraseña del rol de aplicación ----------
-- ---------- 009_subsidios: dimensión opcional de APS/municipio para el balance FSRI ----------
ALTER TABLE carga_mensual_detalle ADD COLUMN IF NOT EXISTS municipio text;
CREATE INDEX IF NOT EXISTS ix_cmd_mpio ON carga_mensual_detalle(empresa_id, municipio);

ALTER ROLE app_user LOGIN PASSWORD 'CAMBIA_ESTA_CLAVE_app';
