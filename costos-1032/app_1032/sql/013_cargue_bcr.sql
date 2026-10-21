-- =====================================================================
--  013_cargue_bcr.sql — Costos particulares (1032) e inventario de la BCR.
--
--  · costo_particular: costos particulares que reconoce la metodología, por año
--    y servicio (insumo del menú «Cargar información», pestaña Costos particulares).
--  · bcr_activo: inventario activo-por-activo de la Base de Capital Regulada, por
--    los tres componentes del art. 2.1.2.1.3.5.18 (1-infraestructura,
--    2-inversiones ambientales y de gestión del riesgo, 3-activos administrativos
--    y operativos). Alimenta el CMI_BCR y la proyección del CMI. Rol dueño (postgres).
-- =====================================================================

-- ---------- Costos particulares (Res. CRA 1032) ----------
CREATE TABLE IF NOT EXISTS costo_particular (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio        smallint NOT NULL,                 -- año al que corresponde (→ año tarifario)
  servicio    text NOT NULL DEFAULT 'acueducto', -- acueducto | alcantarillado | general
  categoria   text,                              -- agrupador (p. ej. CMO, CMA, tasas, contratos)
  concepto    text NOT NULL,                     -- descripción del costo particular
  valor       double precision,                  -- valor ($)
  unidad      text,                              -- $/mes, $/m³, $ total…
  soporte     text,                              -- referencia del soporte
  origen      text NOT NULL DEFAULT 'empresa',   -- empresa | SUI | supuesto
  observacion text,
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, concepto),
  CHECK (servicio IN ('acueducto','alcantarillado','general'))
);
CREATE INDEX IF NOT EXISTS ix_cpart_emp ON costo_particular(empresa_id);

-- ---------- Inventario de activos de la BCR ----------
CREATE TABLE IF NOT EXISTS bcr_activo (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio        text NOT NULL,                 -- acueducto | alcantarillado
  componente      smallint NOT NULL,             -- 1 infraestructura | 2 ambiental/riesgo | 3 admin/operativo
  nombre          text NOT NULL,                 -- nombre del activo
  cod_dane        char(5) REFERENCES municipio(cod_dane),  -- APS (opcional)
  valor_bruto     double precision,              -- valor del activo (pesos dic i-1)
  plazo_remanente numeric(6,2),                  -- años de recuperación remanente
  cuota_anual     double precision,              -- cuota anual de recuperación del capital (cak, art. 2.1.2.1.3.5.11)
  valor_pendiente double precision,              -- valor pendiente por recuperar (integra la BCR)
  origen          text NOT NULL DEFAULT 'BCR0',  -- BCR0_688 | BCR0_825 | POIR | nuevo
  observacion     text,
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  CHECK (servicio IN ('acueducto','alcantarillado')),
  CHECK (componente IN (1,2,3))
);
CREATE INDEX IF NOT EXISTS ix_bcr_emp ON bcr_activo(empresa_id);
CREATE INDEX IF NOT EXISTS ix_bcr_emp_serv ON bcr_activo(empresa_id, servicio);

-- ---------- RLS por empresa ----------
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

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON costo_particular, bcr_activo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE costo_particular_id_seq, bcr_activo_id_seq TO app_user;
