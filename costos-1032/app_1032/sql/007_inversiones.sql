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
