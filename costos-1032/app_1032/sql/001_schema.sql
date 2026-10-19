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
