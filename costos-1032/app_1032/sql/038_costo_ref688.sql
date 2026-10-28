-- =====================================================================
--  038_costo_ref688.sql — Último costo de referencia del marco 688 (punto de partida).
--
--  Insumo EXCLUSIVO del período de inicio (art. 2.1.2.1.1.8 de la Res. CRA 1032/2026):
--  registra, por servicio, el último costo económico de referencia / tarifa que la
--  persona prestadora venía aplicando bajo la metodología anterior (Res. CRA 688/2014
--  y modificatorias) y la FECHA a la que esos valores estaban indexados. Es el punto
--  de partida para la transición y la comparación con los costos de la nueva metodología.
--
--  Se capturan tanto la tarifa aplicada (cargo fijo y cargo por consumo) como —cuando
--  la empresa la tenga— la desagregación por componente (CMA/CMO/CMI/CMICT), más el
--  acto administrativo con que se aplicó y el índice usado en la última indexación.
--  Idempotente; RLS por empresa; grants a app_user.
-- =====================================================================

CREATE TABLE IF NOT EXISTS costo_referencia_688 (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio        text NOT NULL,                     -- acueducto | alcantarillado
  cargo_fijo      double precision,                  -- CF 688 aplicado ($/suscriptor-mes) = CMA
  cargo_consumo   double precision,                  -- CC 688 aplicado ($/m³) = CMO+CMI(+tasas)
  cma             double precision,                  -- desagregación opcional ($/susc-mes)
  cmo             double precision,                  -- ($/m³)
  cmi             double precision,                  -- ($/m³)
  cmict           double precision,                  -- ($/m³) tasas/impuestos, si se separaban
  fecha_indexacion date,                             -- fecha a la que estaban indexados los valores
  indice_base     double precision,                  -- índice (IPC) usado en la última actualización
  acto_admin      text,                              -- resolución/acto administrativo con que se aplicó
  observacion     text,
  origen          text NOT NULL DEFAULT 'empresa',   -- empresa | SUI | supuesto
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, servicio),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);
CREATE INDEX IF NOT EXISTS costo_ref688_idx ON costo_referencia_688 (empresa_id, servicio);

ALTER TABLE costo_referencia_688 ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cr688_all ON costo_referencia_688;
CREATE POLICY cr688_all ON costo_referencia_688 FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON costo_referencia_688 TO app_user;
GRANT USAGE, SELECT ON SEQUENCE costo_referencia_688_id_seq TO app_user;
