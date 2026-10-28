-- =====================================================================
--  042_fecha_inicio_1032.sql — Fecha de inicio de aplicación de la Res. 1032 por empresa.
--
--  El período de inicio (art. 2.1.2.1.1.8) arranca por defecto el 1-jul-2026, pero una
--  empresa puede empezar a aplicar la nueva metodología MÁS TARDE. Esta fecha marca el fin
--  de la aplicación de la 688 (el mes anterior) y, con ello: (i) la duración `t` de la 688
--  para traer el VPR₀ a valor presente y (ii) la cobertura mensual exigida de m³ facturados
--  688 (desde el inicio de la 688 hasta el mes previo al inicio de la 1032).
--
--  Por defecto 2026-07-01 (el estándar), de modo que las empresas ya cargadas no cambian;
--  las que aplicaron más tarde ajustan esta fecha. Idempotente.
-- =====================================================================

ALTER TABLE empresa ADD COLUMN IF NOT EXISTS fecha_inicio_1032 date NOT NULL DEFAULT '2026-07-01';
