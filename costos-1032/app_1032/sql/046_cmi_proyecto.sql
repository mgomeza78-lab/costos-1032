-- =====================================================================
--  046_cmi_proyecto.sql — Detalle de proyectos que sustentan el CMI de la 688 (Paso 02).
--
--  Carga el CMI688 INDIVIDUAL de cada proyecto/activo, separado por COMPONENTE
--  (bcr = BCR₀; poir = POIR) y por TRAMO (período en que el CMI total se mantuvo
--  estable, según la validación del Paso 01). Un archivo por tramo y componente.
--  Regla de verificación (art. 2.1.2.1.3.5.5): para cada servicio y tramo,
--    Σ cmi de los proyectos del componente = CMI_BCR (o CMI_POIR) total del tramo.
--  El nº mínimo de tramos lo fija el Paso 01 (una modificación → dos tramos); el
--  usuario puede cargar tramos adicionales si hubo reconfiguraciones internas que
--  no cambiaron el total del componente pero sí los valores individuales.
--  Idempotente.
-- =====================================================================

CREATE TABLE IF NOT EXISTS cmi_proyecto (
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  tipo            text NOT NULL,           -- 'bcr' | 'poir'
  servicio        text NOT NULL,           -- acueducto | alcantarillado
  tramo           smallint NOT NULL,       -- índice del tramo (1..N) del Paso 01
  id_activo       text NOT NULL,           -- ID del proyecto/activo
  nombre          text,
  cmi             double precision,        -- CMI688 individual del proyecto ($/m³ dic-2014) [OBLIGATORIO]
  -- información de soporte del proyecto (formato oficial BCR0 CRA / AMB); persiste entre tramos:
  vida_util       double precision,        -- VU (años)
  prr             double precision,        -- PRR = VU − t (plazo de recuperación remanente, años)
  anio_operacion  smallint,                -- año de entrada en operación
  valor_via688    double precision,        -- VIA688 / Valor BCR0 ($dic-2014)
  vp_cmi_q        double precision,        -- VP(CMI×Q) del activo ($dic-2014)
  vpr0            double precision,        -- VPR₀ = VIA − VP(CMI×Q)
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, tipo, servicio, tramo, id_activo)
);
CREATE INDEX IF NOT EXISTS ix_cmiproy ON cmi_proyecto(empresa_id, tipo, servicio, tramo);
-- idempotente para tablas ya creadas sin la columna:
ALTER TABLE cmi_proyecto ADD COLUMN IF NOT EXISTS prr double precision;

ALTER TABLE cmi_proyecto ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cmiproy_all ON cmi_proyecto;
CREATE POLICY cmiproy_all ON cmi_proyecto FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON cmi_proyecto TO app_user;
