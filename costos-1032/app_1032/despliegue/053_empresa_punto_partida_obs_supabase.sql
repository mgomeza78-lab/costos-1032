-- 053_empresa_punto_partida_obs_supabase.sql — Observación del punto de partida 688 + arrastre desde el Fap. Ejecutar en Supabase (editor SQL). Idéntico a sql/053_empresa_punto_partida_obs.sql.

-- =====================================================================
--  053_empresa_punto_partida_obs.sql — Observación/fuente del punto de partida 688
--  y arrastre de lo que se hubiera cargado antes en el Fap.
--
--  (1) Nota libre de trazabilidad de los datos de transición 688 que se capturan en
--      «Punto de partida» (fecha de inicio 688, suscriptores del segmento y metas del IPUF
--      de los años tarifarios 9 y 10): de dónde se tomaron. Queda junto a esos datos.
--  (2) Arrastre único: las metas del IPUF (y la observación) que se hubieran digitado antes
--      en la sección del Fap (ccp_fap) se copian a la empresa, para no perderlas al mover la
--      captura a «Punto de partida». Sólo rellena lo que esté vacío (COALESCE).
--  Rol dueño (postgres). Idempotente.
-- =====================================================================

ALTER TABLE empresa ADD COLUMN IF NOT EXISTS punto_partida_obs text;
-- Guardas por si la 052 no se corrió antes (idempotentes).
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS ipuf_meta_688_a9  double precision;
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS ipuf_meta_688_a10 double precision;

-- Arrastre desde el Fap (ccp_fap) → empresa, sin pisar lo ya cargado.
UPDATE empresa e SET
  ipuf_meta_688_a9  = COALESCE(e.ipuf_meta_688_a9,  f.ipuf_meta_a9),
  ipuf_meta_688_a10 = COALESCE(e.ipuf_meta_688_a10, f.ipuf_meta_a10),
  punto_partida_obs = COALESCE(e.punto_partida_obs, f.observacion)
FROM ccp_fap f
WHERE f.empresa_id = e.id
  AND (f.ipuf_meta_a9 IS NOT NULL OR f.ipuf_meta_a10 IS NOT NULL OR f.observacion IS NOT NULL);

COMMENT ON COLUMN empresa.punto_partida_obs IS
  'Observación/fuente de los datos del punto de partida 688 (fecha de inicio, suscriptores del segmento y metas del IPUF años 9 y 10): de dónde se tomaron, para auditoría.';
