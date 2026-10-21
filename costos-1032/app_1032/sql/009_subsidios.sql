-- =====================================================================
--  009_subsidios.sql — soporte del Balance de Subsidios y Contribuciones
--  (Fondo de Solidaridad y Redistribución de Ingresos — FSRI).
--
--  El balance se calcula AL VUELO (subsidios_service.py) desde lo que ya se
--  carga mes a mes: carga_mensual_detalle (comercial del SUI por clase),
--  factor_subsidio (factores) y tarifa_vigente (tarifa mensual). No requiere
--  tablas de resultados nuevas.
--
--  Esta migración solo agrega la dimensión OPCIONAL de APS/municipio, para
--  poder separar el balance por área de prestación (el FSRI es municipal;
--  p. ej. Las Ceibas atiende Neiva y Palermo, que se radican por separado).
--  Si la columna queda nula, el balance se agrupa bajo el municipio de la
--  empresa (una sola APS). Se ejecuta como el rol dueño (postgres).
-- =====================================================================

ALTER TABLE carga_mensual_detalle ADD COLUMN IF NOT EXISTS municipio text;

CREATE INDEX IF NOT EXISTS ix_cmd_mpio ON carga_mensual_detalle(empresa_id, municipio);
