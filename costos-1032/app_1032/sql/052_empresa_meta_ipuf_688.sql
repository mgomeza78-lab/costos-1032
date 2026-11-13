-- =====================================================================
--  052_empresa_meta_ipuf_688.sql — Metas del IPUF de la 688 (años tarifarios 9 y 10).
--
--  Son dato del "punto de partida" (como la fecha de inicio de la 688 y los suscriptores
--  del segmento): la meta de pérdidas que el prestador se había comprometido en su estudio
--  688 para los dos últimos años tarifarios. El sistema las usa para validar el cumplimiento
--  de meta del Fap del CCP (diferencia ≤ 20 %, parágrafo 3 del art. 2.1.2.1.3.3.1). Se
--  capturan en «Punto de partida», no en la sección del Fap.
--  Rol dueño (postgres). Idempotente.
-- =====================================================================

ALTER TABLE empresa ADD COLUMN IF NOT EXISTS ipuf_meta_688_a9  double precision;  -- meta IPUF 688, año tarifario 9
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS ipuf_meta_688_a10 double precision;  -- meta IPUF 688, año tarifario 10

COMMENT ON COLUMN empresa.ipuf_meta_688_a9  IS 'Meta del IPUF (m³/susc·mes) del año tarifario 9 de la Res. 688, del estudio del prestador. Punto de partida.';
COMMENT ON COLUMN empresa.ipuf_meta_688_a10 IS 'Meta del IPUF (m³/susc·mes) del año tarifario 10 de la Res. 688, del estudio del prestador. Punto de partida.';
