-- =====================================================================
--  012_aps_supabase.sql — Área de Prestación del Servicio (APS) en Supabase.
--  Delta para el entorno gestionado. Ejecutar en el SQL Editor de Supabase
--  DESPUÉS de 010_territorio y 011_divipola_data (requiere empresa, municipio,
--  usuario, app_user y las funciones app_allow_all()/app_empresa_ids()).
--  Contenido idéntico a sql/012_aps.sql (portable).
-- =====================================================================

-- =====================================================================
--  012_aps.sql — Área de Prestación del Servicio (APS).
--
--  Captura los criterios regulatorios para el establecimiento del APS del
--  art. 2.1.2.1.1.5 de la Res. CRA 1032 de 2026. Se establece UN APS por cada
--  municipio/distrito que atiende la empresa (un registro por empresa_id +
--  cod_dane, apoyado en empresa_municipio de la migración 010).
--
--  Además, aps_archivo guarda los soportes que la 1032 exige o sugiere por APS
--  (mapa y coordenadas georreferenciadas, instrumento de ordenamiento, Plan
--  Maestro, reporte al municipio, etc.) en los formatos Excel/CSV/PDF e imágenes
--  o archivos geográficos del polígono. Rol dueño (postgres).
-- =====================================================================

-- ---------- APS (un registro por municipio del prestador) ----------
CREATE TABLE IF NOT EXISTS aps (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  cod_dane       char(5) REFERENCES municipio(cod_dane),   -- municipio/distrito del APS (DIVIPOLA)
  numero_aps     smallint,                                 -- número/identificador del APS en la empresa
  nombre         text,                                     -- rótulo del APS (p. ej. «APS Neiva»)
  codigo_aps     text,                                     -- código propio / id del APS en el SUI (si aplica)

  -- Servicios que presta en el municipio (art. 2.1.2.1.1.5)
  servicios              text NOT NULL DEFAULT 'ambos',    -- ac | al | ambos
  aps_difiere_servicios  boolean NOT NULL DEFAULT false,   -- APS distinta por servicio (solo uno / fuentes alternas / criterios ambientales)

  -- Zonas de prestación
  zona           text NOT NULL DEFAULT 'urbana',           -- urbana | urbana_rural
  sistema_rural  text NOT NULL DEFAULT 'na',               -- na | integrado | no_integrado_urbana | no_integrado_urbano_rural

  -- Configuración regional (esquemas que atienden dos o más municipios)
  esquema_regional        boolean NOT NULL DEFAULT false,
  sistema_interconexion   text NOT NULL DEFAULT 'na',      -- na | interconectado | no_interconectado | mixto
  tipo_regional           text NOT NULL DEFAULT 'na',      -- na | mercado_regional | costos_unificados | no_unificados
  mercado_regional_declarado boolean NOT NULL DEFAULT false,

  -- Condiciones especiales / APS de menor tamaño (art. 2.1.2.1.1.5 y condición especial)
  aplicaba_825   boolean NOT NULL DEFAULT false,           -- le resultaba aplicable la Res. CRA 825 de 2017
  menor_5000     boolean NOT NULL DEFAULT false,           -- APS con 5.000 suscriptores o menos
  pdet           boolean NOT NULL DEFAULT false,           -- municipio PDET (Decreto Ley 893 de 2017)
  zomac          boolean NOT NULL DEFAULT false,           -- ZOMAC (art. 236 Ley 1819 de 2016)
  ed_particular  boolean NOT NULL DEFAULT false,           -- esquema diferencial de prestación en condición particular
  ed_urbano_zdu  boolean NOT NULL DEFAULT false,           -- esquema diferencial urbano (ZDU, área de difícil gestión)
  ed_rural_zrni  boolean NOT NULL DEFAULT false,           -- zona rural con sistema no integrado (ZRNI)
  toma_posesion_sspd boolean NOT NULL DEFAULT false,       -- en toma de posesión por la SSPD

  -- Georreferenciación (se mantiene de la Res. CRA 688; MAGNA-SIRGAS)
  georref_sistema    text NOT NULL DEFAULT 'MAGNA-SIRGAS',
  georref_presentada boolean NOT NULL DEFAULT false,       -- se adjuntó mapa + polígono + listado de coordenadas
  area_ha            numeric(14,2),                        -- área del APS en hectáreas (opcional)

  -- Ordenamiento del territorio y reporte al municipio
  instrumento_ot      text,                                -- POT | PBOT | EOT
  instrumento_ot_acto text,                                -- acto que lo adopta (acuerdo/decreto n.º y año)
  pmaa                boolean NOT NULL DEFAULT false,       -- cuenta con Plan Maestro de Acueducto y Alcantarillado
  reportado_municipio boolean NOT NULL DEFAULT false,      -- APS reportada al municipio/distrito
  reportado_fecha     date,
  reportado_acto      text,

  observacion     text,
  actualizado_por integer REFERENCES usuario(id),
  creado_en       timestamptz NOT NULL DEFAULT now(),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, cod_dane),
  CHECK (servicios     IN ('ac','al','ambos')),
  CHECK (zona          IN ('urbana','urbana_rural')),
  CHECK (sistema_rural IN ('na','integrado','no_integrado_urbana','no_integrado_urbano_rural')),
  CHECK (sistema_interconexion IN ('na','interconectado','no_interconectado','mixto')),
  CHECK (tipo_regional IN ('na','mercado_regional','costos_unificados','no_unificados')),
  CHECK (instrumento_ot IS NULL OR instrumento_ot IN ('POT','PBOT','EOT'))
);
CREATE INDEX IF NOT EXISTS ix_aps_emp ON aps(empresa_id);

-- ---------- Soportes documentales por APS (Excel/CSV/PDF/imagen/geo) ----------
CREATE TABLE IF NOT EXISTS aps_archivo (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  aps_id      integer NOT NULL REFERENCES aps(id) ON DELETE CASCADE,
  categoria   text NOT NULL,            -- georreferenciacion | pot_pbot_eot | pmaa | reporte_municipio | soporte_825 | soporte_general
  nombre      text NOT NULL,            -- nombre original del archivo
  tipo        text,                     -- extensión/tipo (pdf, xlsx, csv, png, kml…)
  tamano      integer,                  -- tamaño en bytes
  contenido   bytea NOT NULL,           -- contenido del archivo
  subido_por  integer REFERENCES usuario(id),
  subido_en   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_apsarch_emp ON aps_archivo(empresa_id);
CREATE INDEX IF NOT EXISTS ix_apsarch_aps ON aps_archivo(aps_id);

-- ---------- RLS por empresa ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON aps, aps_archivo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE aps_id_seq, aps_archivo_id_seq TO app_user;
