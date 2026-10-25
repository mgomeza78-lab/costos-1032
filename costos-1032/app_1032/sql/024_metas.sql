-- =====================================================================
--  024_metas.sql — Seguimiento a las metas para alcanzar los estándares
--  de prestación de la Resolución CRA 1032 de 2026 (Capítulo 2, arts.
--  2.1.2.1.2.1 y 2.1.2.1.2.2).
--
--  (1) meta_catalogo  : catálogo GLOBAL de los estándares/indicadores de
--      la 1032 (IDH1..IDH14, IRD1..IRD12), por servicio. Datos de
--      referencia sembrados aquí mismo (ON CONFLICT DO NOTHING).
--  (2) meta_empresa   : seguimiento por empresa (línea base cierre 2026,
--      meta proyectada, estado, observación). En el período de inicio las
--      metas solo se identifican/enuncian; su cuantificación se realiza en
--      el primer recálculo (a más tardar 31-may-2027, art. 2.1.2.1.2.1
--      parágrafo 2), con línea base al cierre de 2026.
--  (3) meta_archivo   : soporte documental por meta y empresa.
--  Se ejecuta como el rol dueño.
-- =====================================================================

-- ---------- (1) Catálogo global de estándares (referencia) ----------
CREATE TABLE IF NOT EXISTS meta_catalogo (
  id             serial PRIMARY KEY,
  codigo         text NOT NULL,            -- IDH1, IRD1, …
  servicio       text NOT NULL,            -- acueducto | alcantarillado
  objetivo       text NOT NULL,            -- DHAS | Retos del desarrollo sostenible
  factor         text,                     -- Accesibilidad, Disponibilidad, Calidad, …
  nombre         text NOT NULL,
  tipo           text NOT NULL,            -- estandar | buena_practica
  valor_estandar text,                     -- '100 %', 'IRCAP = 1', 'IPUF* = 4 m³/suscriptor·mes', …
  articulo       text DEFAULT '2.1.2.1.2.2',
  orden          smallint,
  UNIQUE (codigo, servicio)
);

ALTER TABLE meta_catalogo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mc_sel ON meta_catalogo;
DROP POLICY IF EXISTS mc_mod ON meta_catalogo;
CREATE POLICY mc_sel ON meta_catalogo FOR SELECT USING (true);
CREATE POLICY mc_mod ON meta_catalogo FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
GRANT SELECT, INSERT, UPDATE, DELETE ON meta_catalogo TO app_user;

-- ---------- (2) Seguimiento por empresa ----------
CREATE TABLE IF NOT EXISTS meta_empresa (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  meta_id         integer NOT NULL REFERENCES meta_catalogo(id) ON DELETE CASCADE,
  linea_base      text,                    -- valor del indicador al cierre 2026 (pendiente)
  meta_valor      text,                    -- meta proyectada (se define en el primer recálculo, 2027)
  anio_meta       smallint,
  estado          text NOT NULL DEFAULT 'pendiente',  -- pendiente | en_proceso | cumplido | no_aplica
  observacion     text,
  actualizado_por integer REFERENCES usuario(id),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, meta_id)
);

ALTER TABLE meta_empresa ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS me_all ON meta_empresa;
CREATE POLICY me_all ON meta_empresa FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON meta_empresa TO app_user;

-- ---------- (3) Soporte documental por meta ----------
CREATE TABLE IF NOT EXISTS meta_archivo (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  meta_id     integer NOT NULL REFERENCES meta_catalogo(id) ON DELETE CASCADE,
  nombre      text NOT NULL,
  tipo        text,
  tamano      integer,
  contenido   bytea NOT NULL,
  subido_por  integer REFERENCES usuario(id),
  subido_en   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE meta_archivo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ma_all ON meta_archivo;
CREATE POLICY ma_all ON meta_archivo FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));
GRANT SELECT, INSERT, UPDATE, DELETE ON meta_archivo TO app_user;

GRANT USAGE, SELECT ON SEQUENCE
  meta_catalogo_id_seq, meta_empresa_id_seq, meta_archivo_id_seq TO app_user;

-- =====================================================================
--  Semilla del catálogo (art. 2.1.2.1.2.2). Valores de estándar para el
--  SEGUNDO SEGMENTO (p. ej. IPUF* = 4 m³/suscriptor·mes, CT = 68 %).
--  Las buenas prácticas son potestativas (parágrafo 2).
-- =====================================================================
INSERT INTO meta_catalogo (codigo, servicio, objetivo, factor, nombre, tipo, valor_estandar, orden) VALUES
 -- ---- ACUEDUCTO · Factores desde el DHAS ----
 ('IDH1','acueducto','DHAS','Accesibilidad – Física','Cobertura del servicio de acueducto','estandar','100 %',1),
 ('IDH2','acueducto','DHAS','Disponibilidad','Continuidad','estandar','IC = 24 h/día',2),
 ('IDH3','acueducto','DHAS','Disponibilidad','Plan de proyección de la demanda – PPD','buena_practica','Elaborar el plan',3),
 ('IDH4','acueducto','DHAS','Disponibilidad','Plan Integral de Prestación – PIP Acueducto','buena_practica','Elaborar el plan',4),
 ('IDH5','acueducto','DHAS','Calidad','Calidad del agua potable','estandar','IRCAP = 1',5),
 ('IDH6','acueducto','DHAS','Acceso a la información y participación','Nivel de satisfacción del usuario – NSU acueducto','estandar','Puntaje ≥ 4 en la encuesta NSU',6),
 ('IDH7','acueducto','DHAS','Acceso a la información y participación','Gestión social en acueducto','buena_practica','Implementar gestión social y/o nudging',7),
 -- ---- ACUEDUCTO · Retos del desarrollo sostenible ----
 ('IRD1','acueducto','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Pérdidas de agua','estandar','IPUF* = 4 m³/suscriptor·mes',8),
 ('IRD2','acueducto','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Plan de reducción de pérdidas – PRP','estandar','Elaborar e implementar el plan',9),
 ('IRD3','acueducto','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Plan de Sostenibilidad Hídrica – PSH','estandar','Elaborar e implementar el plan',10),
 ('IRD4','acueducto','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Reúso en acueducto','buena_practica','Reusar el 10 % de las ARD tratadas',11),
 ('IRD5','acueducto','Retos del desarrollo sostenible','Eficiencia energética','Gestión eficiente de energía – GEE acueducto','estandar','Mejorar la GEE (Plan de GEE)',12),
 ('IRD6','acueducto','Retos del desarrollo sostenible','Fomento de FNCER','Implementación de FNCER en acueducto','buena_practica','Implementar FNCER',13),
 ('IRD7','acueducto','Retos del desarrollo sostenible','Innovación tecnológica','Mejorar la maduración de innovación tecnológica en acueducto','buena_practica','Evaluar y mejorar el nivel de maduración',14),
 -- ---- ALCANTARILLADO · Factores desde el DHAS ----
 ('IDH8','alcantarillado','DHAS','Accesibilidad – Física','Cobertura del servicio de alcantarillado','estandar','100 %',15),
 ('IDH9','alcantarillado','DHAS','Accesibilidad – Física','Diferencia entre suscriptores de Acueducto y Alcantarillado – DACAL','estandar','Reducir el 100 % de la diferencia',16),
 ('IDH10','alcantarillado','DHAS','Accesibilidad – Física','Plan Integral de Prestación – PIP Alcantarillado','buena_practica','Elaborar el plan',17),
 ('IDH11','alcantarillado','DHAS','Calidad','Cobertura de tratamiento de aguas residuales domésticas','estandar','CT = 68 %',18),
 ('IDH12','alcantarillado','DHAS','Calidad','Calidad del vertimiento','estandar','CPSMV = 100 %',19),
 ('IDH13','alcantarillado','DHAS','Acceso a la información y participación','Nivel de satisfacción del usuario – NSU alcantarillado','estandar','Puntaje ≥ 4 en la encuesta NSU',20),
 ('IDH14','alcantarillado','DHAS','Acceso a la información y participación','Gestión social en alcantarillado','buena_practica','Implementar gestión social y/o nudging',21),
 -- ---- ALCANTARILLADO · Retos del desarrollo sostenible ----
 ('IRD3','alcantarillado','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Plan de Sostenibilidad Hídrica – PSH','estandar','Elaborar e implementar el plan',22),
 ('IRD8','alcantarillado','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Sistemas Urbanos de Drenaje Sostenible – SUDS','buena_practica','Implementar SUDS',23),
 ('IRD9','alcantarillado','Retos del desarrollo sostenible','Sostenibilidad y economía circular','Reúso / recirculación en alcantarillado','buena_practica','Reusar y/o recircular las ARD tratadas',24),
 ('IRD10','alcantarillado','Retos del desarrollo sostenible','Eficiencia energética','Gestión eficiente de energía – GEE alcantarillado','estandar','Mejorar la GEE (Plan de GEE)',25),
 ('IRD11','alcantarillado','Retos del desarrollo sostenible','Fomento de FNCER','Implementación de FNCER en alcantarillado','buena_practica','Implementar FNCER',26),
 ('IRD12','alcantarillado','Retos del desarrollo sostenible','Innovación tecnológica','Mejorar la maduración de innovación tecnológica en alcantarillado','buena_practica','Evaluar y mejorar el nivel de maduración',27)
ON CONFLICT (codigo, servicio) DO NOTHING;
