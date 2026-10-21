-- =====================================================================
--  015_poir_cmi.sql — Ingresos por proyecto: CMI por activo y modificaciones del POIR.
--
--  El cálculo de los ingresos recuperados vía CMI (VP(CMI688ⱼ×Qt)) es
--  ACTIVO POR ACTIVO (art. 2.1.2.1.3.5.5). El CMI de la 688 pudo modificarse
--  durante su aplicación (modificaciones del POIR), de modo que un mismo activo
--  puede tener distintos CMI según el período. Se capturan:
--   · poir_modificacion — cuántas modificaciones y en qué fechas (0 = POIR original);
--   · activo_cmi — el CMI de cada activo bajo cada modificación (de un Excel por modificación);
--   · bcr_activo.codigo — identificador del activo/proyecto para enlazar.
--  Rol dueño (postgres).
-- =====================================================================

ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS codigo text;   -- identificador del activo/proyecto
CREATE INDEX IF NOT EXISTS ix_bcr_cod ON bcr_activo(empresa_id, servicio, codigo);

-- ---------- Modificaciones del POIR (0 = original) ----------
CREATE TABLE IF NOT EXISTS poir_modificacion (
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio    text NOT NULL,
  numero      smallint NOT NULL,          -- 0 = POIR original; 1..N = modificaciones
  fecha       date,                        -- fecha de entrada en vigencia de la modificación
  descripcion text,
  PRIMARY KEY (empresa_id, servicio, numero),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- CMI por activo bajo cada modificación ----------
CREATE TABLE IF NOT EXISTS activo_cmi (
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio     text NOT NULL,
  codigo       text NOT NULL,              -- identificador del activo/proyecto
  modificacion smallint NOT NULL,          -- 0..N (enlaza con poir_modificacion.numero)
  cmi          double precision,           -- CMI688 del activo bajo esa modificación ($/m³)
  PRIMARY KEY (empresa_id, servicio, codigo, modificacion),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);
CREATE INDEX IF NOT EXISTS ix_acmi_cod ON activo_cmi(empresa_id, servicio, codigo);

-- ---------- RLS ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON poir_modificacion, activo_cmi TO app_user;
