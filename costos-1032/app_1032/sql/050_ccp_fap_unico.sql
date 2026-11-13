-- =====================================================================
--  050_ccp_fap_unico.sql — El Fap del CCP pasa a ser ÚNICO por prestador.
--
--  Fundamento (Res. CRA 1032, art. 2.1.2.1.3.3.1 y su parágrafo 3): el CCP de
--  AMBOS servicios se construye sobre el ISUF del ACUEDUCTO
--     CCP_ac = (ISUF_ac − IPUF*) · N_ac · 12
--     CCP_al = (ISUF_ac − ICUF_ac + ICUF_al − IPUF*) · N_al · 12
--  y el Fap del parágrafo 3 ajusta ese mismo ISUF_ac (ISUF_ajustado = ISUF − Fap).
--  Por tanto el Fap es UNO SOLO por empresa; no existe un Fap de alcantarillado
--  (el de alcantarillado hereda el IPUF/ISUF del acueducto). Se colapsa la tabla
--  a una fila por empresa y se agregan las metas del IPUF de la 688 de los años
--  tarifarios 9 y 10 (insumo del cumplimiento de meta, que el sistema valida al
--  20 %). La metodología anterior y el IPUFreal ya no se digitan: se derivan del
--  punto de partida (bcr_param.fecha_inicio_688) y de lo cargado.
--  Rol dueño (postgres). Idempotente.
-- =====================================================================

-- (a) Metas del IPUF de la 688 por año tarifario (para el cumplimiento de meta).
ALTER TABLE ccp_fap ADD COLUMN IF NOT EXISTS ipuf_meta_a9  double precision;  -- meta IPUF 688, año tarifario 9
ALTER TABLE ccp_fap ADD COLUMN IF NOT EXISTS ipuf_meta_a10 double precision;  -- meta IPUF 688, año tarifario 10

-- (b) Preserva la meta 688 previa (campo único ipuf_planeado) como meta del año 10.
UPDATE ccp_fap SET ipuf_meta_a10 = ipuf_planeado
 WHERE ipuf_planeado IS NOT NULL AND ipuf_meta_a10 IS NULL;

-- (c) Un solo Fap por prestador: colapsa a la fila de acueducto y recompone la PK.
--     Se ejecuta una sola vez (mientras 'servicio' siga siendo parte de la clave).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.key_column_usage
    WHERE constraint_name = 'ccp_fap_pkey' AND table_name = 'ccp_fap' AND column_name = 'servicio'
  ) THEN
    DELETE FROM ccp_fap WHERE servicio <> 'acueducto';   -- la fila de alcantarillado era redundante
    ALTER TABLE ccp_fap DROP CONSTRAINT ccp_fap_pkey;
    ALTER TABLE ccp_fap ADD  PRIMARY KEY (empresa_id);
  END IF;
END $$;

-- La columna 'servicio' queda vestigial (siempre 'acueducto'); se conserva por
-- compatibilidad y no se vuelve a usar como dimensión.
ALTER TABLE ccp_fap ALTER COLUMN servicio SET DEFAULT 'acueducto';

COMMENT ON COLUMN ccp_fap.servicio      IS 'Vestigial (siempre acueducto): el Fap es único por empresa desde la migración 050.';
COMMENT ON COLUMN ccp_fap.ipuf_real     IS 'IPUFreal de la ventana IRD1 (1-jul-2024/30-jun-2025), calculado por el sistema (no se digita).';
COMMENT ON COLUMN ccp_fap.metodologia   IS 'Derivada del punto de partida (bcr_param.fecha_inicio_688): 688 si hay fecha, si no 825.';
COMMENT ON COLUMN ccp_fap.ipuf_planeado IS 'Meta 688 que gobierna el Fap (= meta del año tarifario 10 si existe, si no la del 9).';
COMMENT ON COLUMN ccp_fap.cumplio_meta  IS 'Cumplimiento de la meta 688 (diferencia ≤ 20 %) que gobierna el Fap; lo calcula el sistema.';
