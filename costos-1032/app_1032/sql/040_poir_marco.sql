-- =====================================================================
--  040_poir_marco.sql — Marco del POIR en proyecto_inversion ('688' / '1032').
--
--  Separa el POIR del marco anterior (Res. CRA 688, insumo HISTÓRICO del período de
--  inicio para reconstruir la BCR₀ y verificar el 80 % de ejecución, art. 2.1.2.1.3.5.14)
--  del POIR de la nueva metodología (Res. CRA 1032, plan PROSPECTIVo que la empresa
--  ejecuta desde el año tarifario 1 y que alimenta la evolución de la BCR y el CMI).
--
--  Los proyectos ya cargados quedan como '688' (no se altera el período de inicio).
--  Idempotente.
-- =====================================================================

ALTER TABLE proyecto_inversion ADD COLUMN IF NOT EXISTS marco text NOT NULL DEFAULT '688';
ALTER TABLE proyecto_inversion DROP CONSTRAINT IF EXISTS proyecto_inversion_marco_chk;
ALTER TABLE proyecto_inversion ADD CONSTRAINT proyecto_inversion_marco_chk CHECK (marco IN ('688','1032'));
CREATE INDEX IF NOT EXISTS ix_pi_marco ON proyecto_inversion(empresa_id, marco);
