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
