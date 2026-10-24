-- =====================================================================
--  018_bcr_serie_segmento.sql — segmento histórico en la serie de agua
--  facturada de la 688.
--
--  El paso 1 de la Base de Capital Regulado captura, por año de aplicación
--  de la 688 y por servicio, el agua facturada (Q), el CMI cobrado y el
--  SEGMENTO al que pertenecía la empresa ese año (pudo cambiar en el tiempo).
--  Idempotente.
-- =====================================================================
ALTER TABLE bcr_serie ADD COLUMN IF NOT EXISTS segmento smallint;
