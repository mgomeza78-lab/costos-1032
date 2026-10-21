-- 017_ccp_fap_supabase.sql — Factor de ajuste del ISUF (Fap) del CCP. Ejecutar en Supabase. Idéntico a sql/017_ccp_fap.sql.

-- =====================================================================
--  017_ccp_fap.sql — Factor de ajuste del ISUF (Fap) para el CCP.
--
--  El CCP admite un ajuste OPTATIVO del ISUF: ISUF_ajustado = ISUF − Fap
--  (parágrafo 3 del artículo del CCP, Res. CRA 1032). El Fap se selecciona de una
--  tabla con cuatro entradas: (a) rango del IPUFreal, (b) Índice de Vulnerabilidad
--  Hídrica -IVH (IDEAM), (c) metodología anterior aplicada (688/825) y (d) para
--  quienes aplicaron la 688, si cumplieron la meta del IPUF (diferencia ≤ 20 %).
--  Para el período de inicio el IPUFreal es el del 1-jul-2024 a 30-jun-2025 (IRD1).
--  Rol dueño (postgres).
-- =====================================================================

CREATE TABLE IF NOT EXISTS ccp_fap (
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio        text NOT NULL DEFAULT 'acueducto',
  aplica          boolean NOT NULL DEFAULT true,   -- el ajuste es optativo
  ipuf_real       double precision,                -- IPUFreal (m³/susc·mes), ventana IRD1
  ipuf_planeado   double precision,                -- IPUF planeado Res. 688 (para el cumplimiento de meta)
  ivh             text,                            -- muy_baja | baja | media | alta | muy_alta
  metodologia     text,                            -- 688 | 825
  cumplio_meta    boolean,                         -- Res. 688: diferencia IPUF ≤ 20 % (N/A para 825)
  periodo         text NOT NULL DEFAULT 'inicio',  -- inicio | recalculo
  fap             double precision,                -- factor resuelto de la tabla
  observacion     text,
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, servicio),
  CHECK (servicio IN ('acueducto','alcantarillado')),
  CHECK (metodologia IS NULL OR metodologia IN ('688','825')),
  CHECK (ivh IS NULL OR ivh IN ('muy_baja','baja','media','alta','muy_alta'))
);

ALTER TABLE ccp_fap ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ccpfap_all ON ccp_fap;
CREATE POLICY ccpfap_all ON ccp_fap FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON ccp_fap TO app_user;
