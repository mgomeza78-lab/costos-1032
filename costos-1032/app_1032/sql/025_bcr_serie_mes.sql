-- =====================================================================
--  025_bcr_serie_mes.sql — La serie de agua facturada de la 688 (BCR₀,
--  art. 2.1.2.1.3.5.5) pasa a ser MENSUAL: el CMI688 cobrado y el agua
--  facturada (Q) pudieron cambiar dentro de un mismo año de la 688, por
--  lo que se captura por (año de la 688, mes). El VP agrega los ingresos
--  mensuales (CMI×Q) dentro de cada año y descuenta por el año i.
--  Se agrega el mes a la clave primaria (0 = sin mes, filas heredadas).
-- =====================================================================
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS mes smallint NOT NULL DEFAULT 0;  -- 1..12 (0 = sin mes)
ALTER TABLE bcr_serie DROP CONSTRAINT IF EXISTS bcr_serie_pkey;
ALTER TABLE bcr_serie ADD PRIMARY KEY (empresa_id, servicio, anio_tarifario, mes);
