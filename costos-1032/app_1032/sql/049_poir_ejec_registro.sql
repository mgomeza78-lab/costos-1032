-- =====================================================================
--  049_poir_ejec_registro.sql — POIR 688: REGISTRO de ejecución (fuente única).
--
--  Registro de la ejecución del POIR por ACTIVO y AÑO TARIFARIO, con la fecha
--  de entrada en operación (hoja 06.3.x del modelo). Es el ÚNICO insumo del POIR
--  ejecutado: al cargarlo, el sistema descuenta todo al inicio de la 688 y calcula
--    · VIA688ⱼ = VPN del ejecutado por año (ancla año 1 = Σ valorₖ/(1+r688)^(k−1)),
--    · VP(CMI×Q)ⱼ con el CMI planeado (Paso 3) y la demanda (Paso 1),
--    · VPR₀ⱼ = (VIA688ⱼ − VP)·(1+r688)^10  → base de capital (Pasos 5 y 6),
--    · y la serie anual ejecutada → % de cumplimiento (VPN).
--  Si un activo se ejecuta en varios años no hay problema: cada año se descuenta
--  por separado. Admite varias filas por (activo, año). Idempotente.
-- =====================================================================

CREATE TABLE IF NOT EXISTS poir_ejec_registro (
  id              bigserial PRIMARY KEY,
  empresa_id      integer  NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  id_activo       text     NOT NULL,          -- id del activo/proyecto (enlaza con el POIR planeado)
  servicio        text     NOT NULL,          -- acueducto | alcantarillado
  anio_tarifario  smallint NOT NULL,          -- 1..10 (año tarifario de la 688)
  valor_ejecutado double precision,           -- capex ejecutado en el año ($dic-2014)
  fecha_operacion date,                        -- fecha de entrada en operación del activo
  vida_util       double precision,            -- vida útil del activo (años)
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_poirejecreg ON poir_ejec_registro(empresa_id, servicio, id_activo);

ALTER TABLE poir_ejec_registro ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poirejecreg_all ON poir_ejec_registro;
CREATE POLICY poirejecreg_all ON poir_ejec_registro FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON poir_ejec_registro TO app_user;
GRANT USAGE, SELECT ON SEQUENCE poir_ejec_registro_id_seq TO app_user;
