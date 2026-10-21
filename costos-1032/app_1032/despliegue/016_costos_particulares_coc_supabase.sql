-- 016_costos_particulares_coc_supabase.sql — Costos particulares: cuenta/valor contable (resta del COC), cantidad y precio unitario.
-- Ejecutar en Supabase DESPUÉS de 013. Idéntico a sql/016_costos_particulares_coc.sql.

-- =====================================================================
--  016_costos_particulares_coc.sql — Costos particulares alineados a los modelos
--  y su resta del COC (para no doble contar).
--
--  Los costos operativos particulares (COP: energía, insumos químicos,
--  tratamiento, contratos; art. 2.1.2.1.3.4.5) se reconocen aparte del Costo
--  Operativo Comparable (COC, art. 2.1.2.1.3.4.4). Si el costo particular ya está
--  registrado en la contabilidad que alimenta el COC, debe restarse del COC para
--  no duplicar su reconocimiento. Por eso se capturan, por costo particular:
--   · cuenta_contable y valor_contable (valor registrado en el año tarifario) → resta del COC;
--   · cantidad y precio_unitario (como en los modelos: p. ej. energía kWh × $/kWh).
--  Rol dueño (postgres).
-- =====================================================================

ALTER TABLE costo_particular ADD COLUMN IF NOT EXISTS cuenta_contable  text;             -- cuenta del PUC registrada
ALTER TABLE costo_particular ADD COLUMN IF NOT EXISTS valor_contable   double precision;  -- valor contable en el año tarifario (se resta del COC)
ALTER TABLE costo_particular ADD COLUMN IF NOT EXISTS cantidad         double precision;  -- cantidad (kWh, kg…) como en los modelos
ALTER TABLE costo_particular ADD COLUMN IF NOT EXISTS precio_unitario  double precision;  -- precio unitario ($/unidad)
