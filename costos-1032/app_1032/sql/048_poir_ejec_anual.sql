-- =====================================================================
--  048_poir_ejec_anual.sql — POIR 688: valor EJECUTADO por año tarifario.
--
--  Serie del valor efectivamente ejecutado del POIR (a precios dic-2014), por
--  servicio y AÑO TARIFARIO de la 688 (1..10), tomada del registro/control de
--  ejecución del POIR (hojas 06.3.x del modelo). Alimenta la EVALUACIÓN DE
--  CUMPLIMIENTO del POIR ejecutado (Paso 4): % de ejecución, comparación en
--  VNA/VPR y rezago por servicio.
--
--  El PLANEADO por año NO se guarda aquí: se deriva del POIR planeado
--  (poir_plan, último tramo) agrupando valor_poir por año. El % de ejecución =
--  VNA(ejecutado)/VNA(planeado), con VNA = NPV(r688, serie anual) — hoja
--  06_Seguimiento del modelo. Idempotente.
-- =====================================================================

CREATE TABLE IF NOT EXISTS poir_ejec_anual (
  empresa_id       integer  NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio         text     NOT NULL,          -- acueducto | alcantarillado
  anio_tarifario   smallint NOT NULL,          -- 1..10 (año tarifario de la 688)
  valor_ejecutado  double precision,           -- valor ejecutado del POIR en el año ($dic-2014)
  cargado_por      integer REFERENCES usuario(id),
  cargado_en       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, servicio, anio_tarifario)
);

ALTER TABLE poir_ejec_anual ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poirejecanual_all ON poir_ejec_anual;
CREATE POLICY poirejecanual_all ON poir_ejec_anual FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON poir_ejec_anual TO app_user;

-- ---------------------------------------------------------------------
--  Seed Las Ceibas: valor ejecutado del POIR por año tarifario, a precios
--  dic-2014. Fuente: modelo "Modelo completo (con reclasificación) - Las
--  Ceibas CRA1032 V2", hoja 06_Seguimiento POIR, filas "POIR Ejecutado"
--  (acueducto y alcantarillado). Información REPORTADA POR LA EMPRESA.
--  Busca la empresa POR NOMBRE (no por id fijo, que cambia entre entornos).
--  Idempotente (solo si existe una empresa cuyo nombre contenga "ceibas").
-- ---------------------------------------------------------------------
INSERT INTO poir_ejec_anual (empresa_id, servicio, anio_tarifario, valor_ejecutado)
SELECT e.id, v.servicio, v.anio, v.valor
FROM (VALUES
  ('acueducto', 1, 8874386075.54),
  ('acueducto', 2, 2409745366.43),
  ('acueducto', 3, 4265229591.85),
  ('acueducto', 4, 3823397041.94),
  ('acueducto', 5, 9856527455.36),
  ('acueducto', 6, 4850362457.39),
  ('acueducto', 7, 6233172957.70),
  ('acueducto', 8, 3701746137.73),
  ('acueducto', 9, 2576861180.52),
  ('acueducto', 10, 5199625997.91),
  ('alcantarillado', 1, 4588694421.19),
  ('alcantarillado', 2, 3270663687.81),
  ('alcantarillado', 3, 5691557003.26),
  ('alcantarillado', 4, 8644945991.23),
  ('alcantarillado', 5, 13663102104.75),
  ('alcantarillado', 6, 5936047558.46),
  ('alcantarillado', 7, 5040556422.30),
  ('alcantarillado', 8, 10062614574.03),
  ('alcantarillado', 9, 7375030690.18),
  ('alcantarillado', 10, 4387741298.01)
) AS v(servicio, anio, valor)
CROSS JOIN LATERAL (
  SELECT id FROM empresa WHERE nombre ILIKE '%ceibas%' ORDER BY id LIMIT 1
) e
ON CONFLICT (empresa_id, servicio, anio_tarifario)
  DO UPDATE SET valor_ejecutado = EXCLUDED.valor_ejecutado;
