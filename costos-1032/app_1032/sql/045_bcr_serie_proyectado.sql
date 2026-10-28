-- =====================================================================
--  045_bcr_serie_proyectado.sql — marca de dato real vs proyectado en la serie 688.
--
--  Permite completar la serie de agua facturada 688 cuando faltan meses de dato real
--  (p. ej. los últimos meses del período 688 que la empresa aún no ha reportado):
--    · `proyectado = 0` → m³ REALES reportados por la empresa (por defecto).
--    · `proyectado = 1` → m³ PROYECTADOS (supuesto de trabajo), para cerrar la serie
--      hasta el mes anterior al inicio de la 1032. Deben reemplazarse por el real
--      cuando la empresa lo entregue.
--  La marca es por fila (servicio, APS, año-688, mes), de modo que un mismo mes puede
--  ser real en una APS y proyectado en otra. No altera el VP(CMI×Q): el VPR₀ usa Q
--  venga real o proyectado, pero la marca deja trazabilidad de qué se proyectó.
--  Idempotente.
-- =====================================================================

ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS proyectado smallint NOT NULL DEFAULT 0;  -- 0 real · 1 proyectado

COMMENT ON COLUMN bcr_serie.proyectado IS 'Origen del Q: 0 = m³ reales (empresa); 1 = m³ proyectados (supuesto para cerrar la serie 688)';
