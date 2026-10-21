-- ============================================================================
--  DESPLIEGUE INCREMENTAL — Supabase (estudios de costos CRA 1032)
--  Ejecutar UNA vez en el SQL Editor de Supabase, sobre la base ya desplegada
--  (que tiene las migraciones 001-008). Cubre: subsidios (009), territorio y
--  DIVIPOLA (010-011), APS (012), BCR/CMI/POIR y costos particulares y Fap
--  (013-017). Es idempotente: puede re-ejecutarse sin romper nada.
--  Requiere el rol app_user y las funciones app_allow_all()/app_empresa_ids()
--  creadas en el despliegue inicial (supabase_setup.sql).
-- ============================================================================


-- ======================= 009_subsidios.sql =======================
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


-- ======================= 010_territorio.sql =======================
-- =====================================================================
--  010_territorio.sql — Territorio (DIVIPOLA), segmentación 1032 y campos
--  de alta de empresa. Se ejecuta como el rol dueño (postgres).
--
--  - Catálogo DIVIPOLA del DANE: departamento y municipio.
--  - empresa_municipio: una empresa puede atender varios municipios
--    (prestadores regionales).
--  - empresa += codigo_sui, n_aps, suscriptores_seg.
--  - Los 4 segmentos de la Res. CRA 1032 (art. 2.1.2.1.1.6), con sus tasas
--    r (art. 2.1.2.1.3.1.7) y kct (art. 2.1.2.1.3.1.8).
-- =====================================================================

-- ---------- Catálogo DIVIPOLA ----------
CREATE TABLE IF NOT EXISTS departamento (
  cod_dane char(2) PRIMARY KEY,          -- código DANE del departamento (p. ej. '41')
  nombre   text NOT NULL
);

CREATE TABLE IF NOT EXISTS municipio (
  cod_dane char(5) PRIMARY KEY,          -- código DANE del municipio (incluye el del depto; '41001')
  cod_dpto char(2) NOT NULL REFERENCES departamento(cod_dane),
  nombre   text NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mun_dpto ON municipio(cod_dpto);

-- ---------- Municipios atendidos por cada empresa (varios) ----------
CREATE TABLE IF NOT EXISTS empresa_municipio (
  empresa_id integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  cod_dane   char(5) NOT NULL REFERENCES municipio(cod_dane),
  PRIMARY KEY (empresa_id, cod_dane)
);
CREATE INDEX IF NOT EXISTS ix_em_empresa ON empresa_municipio(empresa_id);

-- ---------- Campos nuevos de empresa ----------
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS codigo_sui       text;      -- código/ID del prestador en el SUI
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS n_aps            smallint;  -- número de Áreas de Prestación del Servicio
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS suscriptores_seg integer;   -- suscriptores al 31-dic-2024 usados para el segmento

-- ---------- RLS ----------
ALTER TABLE departamento      ENABLE ROW LEVEL SECURITY;
ALTER TABLE municipio         ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresa_municipio ENABLE ROW LEVEL SECURITY;

-- catálogo: lo lee cualquier autenticado; lo escribe admin/analista-todas (allow_all)
DROP POLICY IF EXISTS dpto_sel ON departamento; DROP POLICY IF EXISTS dpto_mod ON departamento;
CREATE POLICY dpto_sel ON departamento FOR SELECT USING (true);
CREATE POLICY dpto_mod ON departamento FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());
DROP POLICY IF EXISTS mun_sel ON municipio; DROP POLICY IF EXISTS mun_mod ON municipio;
CREATE POLICY mun_sel ON municipio FOR SELECT USING (true);
CREATE POLICY mun_mod ON municipio FOR ALL USING (app_allow_all()) WITH CHECK (app_allow_all());

-- empresa_municipio: por empresa permitida
DROP POLICY IF EXISTS em_all ON empresa_municipio;
CREATE POLICY em_all ON empresa_municipio FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON departamento, municipio, empresa_municipio TO app_user;

-- ---------- Segmentos CRA 1032 (art. 2.1.2.1.1.6; r: 2.1.2.1.3.1.7; kct: 2.1.2.1.3.1.8) ----------
INSERT INTO segmento (id,nombre,susc_min,susc_max,r,kct,ipuf_estrella,articulo_r,articulo_kct) VALUES
 (1,'Primer segmento (> 300.000 suscriptores)',       300001, NULL,   0.0858, 0.0178, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (2,'Segundo segmento (90.001 – 300.000 suscriptores)', 90001, 300000, 0.0903, 0.0154, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (3,'Tercer segmento (17.001 – 90.000 suscriptores)',   17001, 90000,  0.0910, 0.0162, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8'),
 (4,'Cuarto segmento (5.001 – 17.000 suscriptores)',     5001, 17000,  0.0910, 0.0203, 6.0, '2.1.2.1.3.1.7','2.1.2.1.3.1.8')
ON CONFLICT (id) DO UPDATE SET nombre=excluded.nombre, susc_min=excluded.susc_min,
 susc_max=excluded.susc_max, r=excluded.r, kct=excluded.kct, ipuf_estrella=excluded.ipuf_estrella,
 articulo_r=excluded.articulo_r, articulo_kct=excluded.articulo_kct;

-- ---------- DIVIPOLA (departamentos y municipios) ----------
-- Los datos (33 departamentos y los 1.122 municipios del DANE) se cargan en la
-- migración 011_divipola_data.sql, como tabla fija del sistema.


-- ======================= 011_divipola_data.sql =======================
-- =====================================================================
--  011_divipola_data.sql — DIVIPOLA del DANE cargado como tabla del
--  sistema (departamentos y municipios). Fuente: DANE, Códigos de
--  municipios (datos.gov.co, dataset xdk5-pm3f). Idempotente (upsert).
--  Requiere la migración 010 (tablas departamento y municipio).
-- =====================================================================

INSERT INTO departamento (cod_dane,nombre) VALUES
 ('05','Antioquia'),
 ('08','Atlántico'),
 ('11','Bogotá, D.C.'),
 ('13','Bolívar'),
 ('15','Boyacá'),
 ('17','Caldas'),
 ('18','Caquetá'),
 ('19','Cauca'),
 ('20','Cesar'),
 ('23','Córdoba'),
 ('25','Cundinamarca'),
 ('27','Chocó'),
 ('41','Huila'),
 ('44','La Guajira'),
 ('47','Magdalena'),
 ('50','Meta'),
 ('52','Nariño'),
 ('54','Norte de Santander'),
 ('63','Quindío'),
 ('66','Risaralda'),
 ('68','Santander'),
 ('70','Sucre'),
 ('73','Tolima'),
 ('76','Valle del Cauca'),
 ('81','Arauca'),
 ('85','Casanare'),
 ('86','Putumayo'),
 ('88','Archipiélago de San Andrés, Providencia y Santa Catalina'),
 ('91','Amazonas'),
 ('94','Guainía'),
 ('95','Guaviare'),
 ('97','Vaupés'),
 ('99','Vichada')
ON CONFLICT (cod_dane) DO UPDATE SET nombre=excluded.nombre;

INSERT INTO municipio (cod_dane,cod_dpto,nombre) VALUES
 ('05001','05','Medellín'),
 ('05002','05','Abejorral'),
 ('05004','05','Abriaquí'),
 ('05021','05','Alejandría'),
 ('05030','05','Amagá'),
 ('05031','05','Amalfi'),
 ('05034','05','Andes'),
 ('05036','05','Angelópolis'),
 ('05038','05','Angostura'),
 ('05040','05','Anorí'),
 ('05042','05','Santa Fé de Antioquia'),
 ('05044','05','Anzá'),
 ('05045','05','Apartadó'),
 ('05051','05','Arboletes'),
 ('05055','05','Argelia'),
 ('05059','05','Armenia'),
 ('05079','05','Barbosa'),
 ('05086','05','Belmira'),
 ('05088','05','Bello'),
 ('05091','05','Betania'),
 ('05093','05','Betulia'),
 ('05101','05','Ciudad Bolívar'),
 ('05107','05','Briceño'),
 ('05113','05','Buriticá'),
 ('05120','05','Cáceres'),
 ('05125','05','Caicedo'),
 ('05129','05','Caldas'),
 ('05134','05','Campamento'),
 ('05138','05','Cañasgordas'),
 ('05142','05','Caracolí'),
 ('05145','05','Caramanta'),
 ('05147','05','Carepa'),
 ('05148','05','El Carmen de Viboral'),
 ('05150','05','Carolina'),
 ('05154','05','Caucasia'),
 ('05172','05','Chigorodó'),
 ('05190','05','Cisneros'),
 ('05197','05','Cocorná'),
 ('05206','05','Concepción'),
 ('05209','05','Concordia'),
 ('05212','05','Copacabana'),
 ('05234','05','Dabeiba'),
 ('05237','05','Donmatías'),
 ('05240','05','Ebéjico'),
 ('05250','05','El Bagre'),
 ('05264','05','Entrerríos'),
 ('05266','05','Envigado'),
 ('05282','05','Fredonia'),
 ('05284','05','Frontino'),
 ('05306','05','Giraldo'),
 ('05308','05','Girardota'),
 ('05310','05','Gómez Plata'),
 ('05313','05','Granada'),
 ('05315','05','Guadalupe'),
 ('05318','05','Guarne'),
 ('05321','05','Guatapé'),
 ('05347','05','Heliconia'),
 ('05353','05','Hispania'),
 ('05360','05','Itagüí'),
 ('05361','05','Ituango'),
 ('05364','05','Jardín'),
 ('05368','05','Jericó'),
 ('05376','05','La Ceja'),
 ('05380','05','La Estrella'),
 ('05390','05','La Pintada'),
 ('05400','05','La Unión'),
 ('05411','05','Liborina'),
 ('05425','05','Maceo'),
 ('05440','05','Marinilla'),
 ('05467','05','Montebello'),
 ('05475','05','Murindó'),
 ('05480','05','Mutatá'),
 ('05483','05','Nariño'),
 ('05490','05','Necoclí'),
 ('05495','05','Nechí'),
 ('05501','05','Olaya'),
 ('05541','05','Peñol'),
 ('05543','05','Peque'),
 ('05576','05','Pueblorrico'),
 ('05579','05','Puerto Berrío'),
 ('05585','05','Puerto Nare'),
 ('05591','05','Puerto Triunfo'),
 ('05604','05','Remedios'),
 ('05607','05','Retiro'),
 ('05615','05','Rionegro'),
 ('05628','05','Sabanalarga'),
 ('05631','05','Sabaneta'),
 ('05642','05','Salgar'),
 ('05647','05','San Andrés de Cuerquía'),
 ('05649','05','San Carlos'),
 ('05652','05','San Francisco'),
 ('05656','05','San Jerónimo'),
 ('05658','05','San José de la Montaña'),
 ('05659','05','San Juan de Urabá'),
 ('05660','05','San Luis'),
 ('05664','05','San Pedro de los Milagros'),
 ('05665','05','San Pedro de Urabá'),
 ('05667','05','San Rafael'),
 ('05670','05','San Roque'),
 ('05674','05','San Vicente Ferrer'),
 ('05679','05','Santa Bárbara'),
 ('05686','05','Santa Rosa de Osos'),
 ('05690','05','Santo Domingo'),
 ('05697','05','El Santuario'),
 ('05736','05','Segovia'),
 ('05756','05','Sonsón'),
 ('05761','05','Sopetrán'),
 ('05789','05','Támesis'),
 ('05790','05','Tarazá'),
 ('05792','05','Tarso'),
 ('05809','05','Titiribí'),
 ('05819','05','Toledo'),
 ('05837','05','Turbo'),
 ('05842','05','Uramita'),
 ('05847','05','Urrao'),
 ('05854','05','Valdivia'),
 ('05856','05','Valparaíso'),
 ('05858','05','Vegachí'),
 ('05861','05','Venecia'),
 ('05873','05','Vigía del Fuerte'),
 ('05885','05','Yalí'),
 ('05887','05','Yarumal'),
 ('05890','05','Yolombó'),
 ('05893','05','Yondó'),
 ('05895','05','Zaragoza'),
 ('08001','08','Barranquilla'),
 ('08078','08','Baranoa'),
 ('08137','08','Campo de la Cruz'),
 ('08141','08','Candelaria'),
 ('08296','08','Galapa'),
 ('08372','08','Juan de Acosta'),
 ('08421','08','Luruaco'),
 ('08433','08','Malambo'),
 ('08436','08','Manatí'),
 ('08520','08','Palmar de Varela'),
 ('08549','08','Piojó'),
 ('08558','08','Polonuevo'),
 ('08560','08','Ponedera'),
 ('08573','08','Puerto Colombia'),
 ('08606','08','Repelón'),
 ('08634','08','Sabanagrande'),
 ('08638','08','Sabanalarga'),
 ('08675','08','Santa Lucía'),
 ('08685','08','Santo Tomás'),
 ('08758','08','Soledad'),
 ('08770','08','Suan'),
 ('08832','08','Tubará'),
 ('08849','08','Usiacurí'),
 ('11001','11','Bogotá, D.C.'),
 ('13001','13','Cartagena de Indias'),
 ('13006','13','Achí'),
 ('13030','13','Altos del Rosario'),
 ('13042','13','Arenal'),
 ('13052','13','Arjona'),
 ('13062','13','Arroyohondo'),
 ('13074','13','Barranco de Loba'),
 ('13140','13','Calamar'),
 ('13160','13','Cantagallo'),
 ('13188','13','Cicuco'),
 ('13212','13','Córdoba'),
 ('13222','13','Clemencia'),
 ('13244','13','El Carmen de Bolívar'),
 ('13248','13','El Guamo'),
 ('13268','13','El Peñón'),
 ('13300','13','Hatillo de Loba'),
 ('13430','13','Magangué'),
 ('13433','13','Mahates'),
 ('13440','13','Margarita'),
 ('13442','13','María la Baja'),
 ('13458','13','Montecristo'),
 ('13468','13','Santa Cruz de Mompox'),
 ('13473','13','Morales'),
 ('13490','13','Norosí'),
 ('13549','13','Pinillos'),
 ('13580','13','Regidor'),
 ('13600','13','Río Viejo'),
 ('13620','13','San Cristóbal'),
 ('13647','13','San Estanislao'),
 ('13650','13','San Fernando'),
 ('13654','13','San Jacinto'),
 ('13655','13','San Jacinto del Cauca'),
 ('13657','13','San Juan Nepomuceno'),
 ('13667','13','San Martín de Loba'),
 ('13670','13','San Pablo'),
 ('13673','13','Santa Catalina'),
 ('13683','13','Santa Rosa'),
 ('13688','13','Santa Rosa del Sur'),
 ('13744','13','Simití'),
 ('13760','13','Soplaviento'),
 ('13780','13','Talaigua Nuevo'),
 ('13810','13','Tiquisio'),
 ('13836','13','Turbaco'),
 ('13838','13','Turbaná'),
 ('13873','13','Villanueva'),
 ('13894','13','Zambrano'),
 ('15001','15','Tunja'),
 ('15022','15','Almeida'),
 ('15047','15','Aquitania'),
 ('15051','15','Arcabuco'),
 ('15087','15','Belén'),
 ('15090','15','Berbeo'),
 ('15092','15','Betéitiva'),
 ('15097','15','Boavita'),
 ('15104','15','Boyacá'),
 ('15106','15','Briceño'),
 ('15109','15','Buenavista'),
 ('15114','15','Busbanzá'),
 ('15131','15','Caldas'),
 ('15135','15','Campohermoso'),
 ('15162','15','Cerinza'),
 ('15172','15','Chinavita'),
 ('15176','15','Chiquinquirá'),
 ('15180','15','Chiscas'),
 ('15183','15','Chita'),
 ('15185','15','Chitaraque'),
 ('15187','15','Chivatá'),
 ('15189','15','Ciénega'),
 ('15204','15','Cómbita'),
 ('15212','15','Coper'),
 ('15215','15','Corrales'),
 ('15218','15','Covarachía'),
 ('15223','15','Cubará'),
 ('15224','15','Cucaita'),
 ('15226','15','Cuítiva'),
 ('15232','15','Chíquiza'),
 ('15236','15','Chivor'),
 ('15238','15','Duitama'),
 ('15244','15','El Cocuy'),
 ('15248','15','El Espino'),
 ('15272','15','Firavitoba'),
 ('15276','15','Floresta'),
 ('15293','15','Gachantivá'),
 ('15296','15','Gámeza'),
 ('15299','15','Garagoa'),
 ('15317','15','Guacamayas'),
 ('15322','15','Guateque'),
 ('15325','15','Guayatá'),
 ('15332','15','Güicán de la Sierra'),
 ('15362','15','Iza'),
 ('15367','15','Jenesano'),
 ('15368','15','Jericó'),
 ('15377','15','Labranzagrande'),
 ('15380','15','La Capilla'),
 ('15401','15','La Victoria'),
 ('15403','15','La Uvita'),
 ('15407','15','Villa de Leyva'),
 ('15425','15','Macanal'),
 ('15442','15','Maripí'),
 ('15455','15','Miraflores'),
 ('15464','15','Mongua'),
 ('15466','15','Monguí'),
 ('15469','15','Moniquirá'),
 ('15476','15','Motavita'),
 ('15480','15','Muzo'),
 ('15491','15','Nobsa'),
 ('15494','15','Nuevo Colón'),
 ('15500','15','Oicatá'),
 ('15507','15','Otanche'),
 ('15511','15','Pachavita'),
 ('15514','15','Páez'),
 ('15516','15','Paipa'),
 ('15518','15','Pajarito'),
 ('15522','15','Panqueba'),
 ('15531','15','Pauna'),
 ('15533','15','Paya'),
 ('15537','15','Paz de Río'),
 ('15542','15','Pesca'),
 ('15550','15','Pisba'),
 ('15572','15','Puerto Boyacá'),
 ('15580','15','Quípama'),
 ('15599','15','Ramiriquí'),
 ('15600','15','Ráquira'),
 ('15621','15','Rondón'),
 ('15632','15','Saboyá'),
 ('15638','15','Sáchica'),
 ('15646','15','Samacá'),
 ('15660','15','San Eduardo'),
 ('15664','15','San José de Pare'),
 ('15667','15','San Luis de Gaceno'),
 ('15673','15','San Mateo'),
 ('15676','15','San Miguel de Sema'),
 ('15681','15','San Pablo de Borbur'),
 ('15686','15','Santana'),
 ('15690','15','Santa María'),
 ('15693','15','Santa Rosa de Viterbo'),
 ('15696','15','Santa Sofía'),
 ('15720','15','Sativanorte'),
 ('15723','15','Sativasur'),
 ('15740','15','Siachoque'),
 ('15753','15','Soatá'),
 ('15755','15','Socotá'),
 ('15757','15','Socha'),
 ('15759','15','Sogamoso'),
 ('15761','15','Somondoco'),
 ('15762','15','Sora'),
 ('15763','15','Sotaquirá'),
 ('15764','15','Soracá'),
 ('15774','15','Susacón'),
 ('15776','15','Sutamarchán'),
 ('15778','15','Sutatenza'),
 ('15790','15','Tasco'),
 ('15798','15','Tenza'),
 ('15804','15','Tibaná'),
 ('15806','15','Tibasosa'),
 ('15808','15','Tinjacá'),
 ('15810','15','Tipacoque'),
 ('15814','15','Toca'),
 ('15816','15','Togüí'),
 ('15820','15','Tópaga'),
 ('15822','15','Tota'),
 ('15832','15','Tununguá'),
 ('15835','15','Turmequé'),
 ('15837','15','Tuta'),
 ('15839','15','Tutazá'),
 ('15842','15','Úmbita'),
 ('15861','15','Ventaquemada'),
 ('15879','15','Viracachá'),
 ('15897','15','Zetaquira'),
 ('17001','17','Manizales'),
 ('17013','17','Aguadas'),
 ('17042','17','Anserma'),
 ('17050','17','Aranzazu'),
 ('17088','17','Belalcázar'),
 ('17174','17','Chinchiná'),
 ('17272','17','Filadelfia'),
 ('17380','17','La Dorada'),
 ('17388','17','La Merced'),
 ('17433','17','Manzanares'),
 ('17442','17','Marmato'),
 ('17444','17','Marquetalia'),
 ('17446','17','Marulanda'),
 ('17486','17','Neira'),
 ('17495','17','Norcasia'),
 ('17513','17','Pácora'),
 ('17524','17','Palestina'),
 ('17541','17','Pensilvania'),
 ('17614','17','Riosucio'),
 ('17616','17','Risaralda'),
 ('17653','17','Salamina'),
 ('17662','17','Samaná'),
 ('17665','17','San José'),
 ('17777','17','Supía'),
 ('17867','17','Victoria'),
 ('17873','17','Villamaría'),
 ('17877','17','Viterbo'),
 ('18001','18','Florencia'),
 ('18029','18','Albania'),
 ('18094','18','Belén de los Andaquíes'),
 ('18150','18','Cartagena del Chairá'),
 ('18205','18','Curillo'),
 ('18247','18','El Doncello'),
 ('18256','18','El Paujíl'),
 ('18410','18','La Montañita'),
 ('18460','18','Milán'),
 ('18479','18','Morelia'),
 ('18592','18','Puerto Rico'),
 ('18610','18','San José del Fragua'),
 ('18753','18','San Vicente del Caguán'),
 ('18756','18','Solano'),
 ('18785','18','Solita'),
 ('18860','18','Valparaíso'),
 ('19001','19','Popayán'),
 ('19022','19','Almaguer'),
 ('19050','19','Argelia'),
 ('19075','19','Balboa'),
 ('19100','19','Bolívar'),
 ('19110','19','Buenos Aires'),
 ('19130','19','Cajibío'),
 ('19137','19','Caldono'),
 ('19142','19','Caloto'),
 ('19212','19','Corinto'),
 ('19256','19','El Tambo'),
 ('19290','19','Florencia'),
 ('19300','19','Guachené'),
 ('19318','19','Guapi'),
 ('19355','19','Inzá'),
 ('19364','19','Jambaló'),
 ('19392','19','La Sierra'),
 ('19397','19','La Vega'),
 ('19418','19','López de Micay'),
 ('19450','19','Mercaderes'),
 ('19455','19','Miranda'),
 ('19473','19','Morales'),
 ('19513','19','Padilla'),
 ('19517','19','Páez'),
 ('19532','19','Patía'),
 ('19533','19','Piamonte'),
 ('19548','19','Piendamó - Tunía'),
 ('19573','19','Puerto Tejada'),
 ('19585','19','Puracé'),
 ('19622','19','Rosas'),
 ('19693','19','San Sebastián'),
 ('19698','19','Santander de Quilichao'),
 ('19701','19','Santa Rosa'),
 ('19743','19','Silvia'),
 ('19760','19','Sotará - Paispamba'),
 ('19780','19','Suárez'),
 ('19785','19','Sucre'),
 ('19807','19','Timbío'),
 ('19809','19','Timbiquí'),
 ('19821','19','Toribío'),
 ('19824','19','Totoró'),
 ('19845','19','Villa Rica'),
 ('20001','20','Valledupar'),
 ('20011','20','Aguachica'),
 ('20013','20','Agustín Codazzi'),
 ('20032','20','Astrea'),
 ('20045','20','Becerril'),
 ('20060','20','Bosconia'),
 ('20175','20','Chimichagua'),
 ('20178','20','Chiriguaná'),
 ('20228','20','Curumaní'),
 ('20238','20','El Copey'),
 ('20250','20','El Paso'),
 ('20295','20','Gamarra'),
 ('20310','20','González'),
 ('20383','20','La Gloria'),
 ('20400','20','La Jagua de Ibirico'),
 ('20443','20','Manaure Balcón del Cesar'),
 ('20517','20','Pailitas'),
 ('20550','20','Pelaya'),
 ('20570','20','Pueblo Bello'),
 ('20614','20','Río de Oro'),
 ('20621','20','La Paz'),
 ('20710','20','San Alberto'),
 ('20750','20','San Diego'),
 ('20770','20','San Martín'),
 ('20787','20','Tamalameque'),
 ('23001','23','Montería'),
 ('23068','23','Ayapel'),
 ('23079','23','Buenavista'),
 ('23090','23','Canalete'),
 ('23162','23','Cereté'),
 ('23168','23','Chimá'),
 ('23182','23','Chinú'),
 ('23189','23','Ciénaga de Oro'),
 ('23300','23','Cotorra'),
 ('23350','23','La Apartada'),
 ('23417','23','Lorica'),
 ('23419','23','Los Córdobas'),
 ('23464','23','Momil'),
 ('23466','23','Montelíbano'),
 ('23500','23','Moñitos'),
 ('23555','23','Planeta Rica'),
 ('23570','23','Pueblo Nuevo'),
 ('23574','23','Puerto Escondido'),
 ('23580','23','Puerto Libertador'),
 ('23586','23','Purísima de la Concepción'),
 ('23660','23','Sahagún'),
 ('23670','23','San Andrés de Sotavento'),
 ('23672','23','San Antero'),
 ('23675','23','San Bernardo del Viento'),
 ('23678','23','San Carlos'),
 ('23682','23','San José de Uré'),
 ('23686','23','San Pelayo'),
 ('23807','23','Tierralta'),
 ('23815','23','Tuchín'),
 ('23855','23','Valencia'),
 ('25001','25','Agua de Dios'),
 ('25019','25','Albán'),
 ('25035','25','Anapoima'),
 ('25040','25','Anolaima'),
 ('25053','25','Arbeláez'),
 ('25086','25','Beltrán'),
 ('25095','25','Bituima'),
 ('25099','25','Bojacá'),
 ('25120','25','Cabrera'),
 ('25123','25','Cachipay'),
 ('25126','25','Cajicá'),
 ('25148','25','Caparrapí'),
 ('25151','25','Cáqueza'),
 ('25154','25','Carmen de Carupa'),
 ('25168','25','Chaguaní'),
 ('25175','25','Chía'),
 ('25178','25','Chipaque'),
 ('25181','25','Choachí'),
 ('25183','25','Chocontá'),
 ('25200','25','Cogua'),
 ('25214','25','Cota'),
 ('25224','25','Cucunubá'),
 ('25245','25','El Colegio'),
 ('25258','25','El Peñón'),
 ('25260','25','El Rosal'),
 ('25269','25','Facatativá'),
 ('25279','25','Fómeque'),
 ('25281','25','Fosca'),
 ('25286','25','Funza'),
 ('25288','25','Fúquene'),
 ('25290','25','Fusagasugá'),
 ('25293','25','Gachalá'),
 ('25295','25','Gachancipá'),
 ('25297','25','Gachetá'),
 ('25299','25','Gama'),
 ('25307','25','Girardot'),
 ('25312','25','Granada'),
 ('25317','25','Guachetá'),
 ('25320','25','Guaduas'),
 ('25322','25','Guasca'),
 ('25324','25','Guataquí'),
 ('25326','25','Guatavita'),
 ('25328','25','Guayabal de Síquima'),
 ('25335','25','Guayabetal'),
 ('25339','25','Gutiérrez'),
 ('25368','25','Jerusalén'),
 ('25372','25','Junín'),
 ('25377','25','La Calera'),
 ('25386','25','La Mesa'),
 ('25394','25','La Palma'),
 ('25398','25','La Peña'),
 ('25402','25','La Vega'),
 ('25407','25','Lenguazaque'),
 ('25426','25','Machetá'),
 ('25430','25','Madrid'),
 ('25436','25','Manta'),
 ('25438','25','Medina'),
 ('25473','25','Mosquera'),
 ('25483','25','Nariño'),
 ('25486','25','Nemocón'),
 ('25488','25','Nilo'),
 ('25489','25','Nimaima'),
 ('25491','25','Nocaima'),
 ('25506','25','Venecia'),
 ('25513','25','Pacho'),
 ('25518','25','Paime'),
 ('25524','25','Pandi'),
 ('25530','25','Paratebueno'),
 ('25535','25','Pasca'),
 ('25572','25','Puerto Salgar'),
 ('25580','25','Pulí'),
 ('25592','25','Quebradanegra'),
 ('25594','25','Quetame'),
 ('25596','25','Quipile'),
 ('25599','25','Apulo'),
 ('25612','25','Ricaurte'),
 ('25645','25','San Antonio del Tequendama'),
 ('25649','25','San Bernardo'),
 ('25653','25','San Cayetano'),
 ('25658','25','San Francisco'),
 ('25662','25','San Juan de Rioseco'),
 ('25718','25','Sasaima'),
 ('25736','25','Sesquilé'),
 ('25740','25','Sibaté'),
 ('25743','25','Silvania'),
 ('25745','25','Simijaca'),
 ('25754','25','Soacha'),
 ('25758','25','Sopó'),
 ('25769','25','Subachoque'),
 ('25772','25','Suesca'),
 ('25777','25','Supatá'),
 ('25779','25','Susa'),
 ('25781','25','Sutatausa'),
 ('25785','25','Tabio'),
 ('25793','25','Tausa'),
 ('25797','25','Tena'),
 ('25799','25','Tenjo'),
 ('25805','25','Tibacuy'),
 ('25807','25','Tibirita'),
 ('25815','25','Tocaima'),
 ('25817','25','Tocancipá'),
 ('25823','25','Topaipí'),
 ('25839','25','Ubalá'),
 ('25841','25','Ubaque'),
 ('25843','25','Villa de San Diego de Ubaté'),
 ('25845','25','Une'),
 ('25851','25','Útica'),
 ('25862','25','Vergara'),
 ('25867','25','Vianí'),
 ('25871','25','Villagómez'),
 ('25873','25','Villapinzón'),
 ('25875','25','Villeta'),
 ('25878','25','Viotá'),
 ('25885','25','Yacopí'),
 ('25898','25','Zipacón'),
 ('25899','25','Zipaquirá'),
 ('27001','27','Quibdó'),
 ('27006','27','Acandí'),
 ('27025','27','Alto Baudó'),
 ('27050','27','Atrato'),
 ('27073','27','Bagadó'),
 ('27075','27','Bahía Solano'),
 ('27077','27','Bajo Baudó'),
 ('27099','27','Bojayá'),
 ('27135','27','El Cantón del San Pablo'),
 ('27150','27','Carmen del Darién'),
 ('27160','27','Cértegui'),
 ('27205','27','Condoto'),
 ('27245','27','El Carmen de Atrato'),
 ('27250','27','El Litoral del San Juan'),
 ('27361','27','Istmina'),
 ('27372','27','Juradó'),
 ('27413','27','Lloró'),
 ('27425','27','Medio Atrato'),
 ('27430','27','Medio Baudó'),
 ('27450','27','Medio San Juan'),
 ('27491','27','Nóvita'),
 ('27493','27','Nuevo Belén de Bajirá'),
 ('27495','27','Nuquí'),
 ('27580','27','Río Iró'),
 ('27600','27','Río Quito'),
 ('27615','27','Riosucio'),
 ('27660','27','San José del Palmar'),
 ('27745','27','Sipí'),
 ('27787','27','Tadó'),
 ('27800','27','Unguía'),
 ('27810','27','Unión Panamericana'),
 ('41001','41','Neiva'),
 ('41006','41','Acevedo'),
 ('41013','41','Agrado'),
 ('41016','41','Aipe'),
 ('41020','41','Algeciras'),
 ('41026','41','Altamira'),
 ('41078','41','Baraya'),
 ('41132','41','Campoalegre'),
 ('41206','41','Colombia'),
 ('41244','41','Elías'),
 ('41298','41','Garzón'),
 ('41306','41','Gigante'),
 ('41319','41','Guadalupe'),
 ('41349','41','Hobo'),
 ('41357','41','Íquira'),
 ('41359','41','Isnos'),
 ('41378','41','La Argentina'),
 ('41396','41','La Plata'),
 ('41483','41','Nátaga'),
 ('41503','41','Oporapa'),
 ('41518','41','Paicol'),
 ('41524','41','Palermo'),
 ('41530','41','Palestina'),
 ('41548','41','Pital'),
 ('41551','41','Pitalito'),
 ('41615','41','Rivera'),
 ('41660','41','Saladoblanco'),
 ('41668','41','San Agustín'),
 ('41676','41','Santa María'),
 ('41770','41','Suaza'),
 ('41791','41','Tarqui'),
 ('41797','41','Tesalia'),
 ('41799','41','Tello'),
 ('41801','41','Teruel'),
 ('41807','41','Timaná'),
 ('41872','41','Villavieja'),
 ('41885','41','Yaguará'),
 ('44001','44','Riohacha'),
 ('44035','44','Albania'),
 ('44078','44','Barrancas'),
 ('44090','44','Dibulla'),
 ('44098','44','Distracción'),
 ('44110','44','El Molino'),
 ('44279','44','Fonseca'),
 ('44378','44','Hatonuevo'),
 ('44420','44','La Jagua del Pilar'),
 ('44430','44','Maicao'),
 ('44560','44','Manaure'),
 ('44650','44','San Juan del Cesar'),
 ('44847','44','Uribia'),
 ('44855','44','Urumita'),
 ('44874','44','Villanueva'),
 ('47001','47','Santa Marta'),
 ('47030','47','Algarrobo'),
 ('47053','47','Aracataca'),
 ('47058','47','Ariguaní'),
 ('47161','47','Cerro de San Antonio'),
 ('47170','47','Chivolo'),
 ('47189','47','Ciénaga'),
 ('47205','47','Concordia'),
 ('47245','47','El Banco'),
 ('47258','47','El Piñón'),
 ('47268','47','El Retén'),
 ('47288','47','Fundación'),
 ('47318','47','Guamal'),
 ('47460','47','Nueva Granada'),
 ('47541','47','Pedraza'),
 ('47545','47','Pijiño del Carmen'),
 ('47551','47','Pivijay'),
 ('47555','47','Plato'),
 ('47570','47','Puebloviejo'),
 ('47605','47','Remolino'),
 ('47660','47','Sabanas de San Ángel'),
 ('47675','47','Salamina'),
 ('47692','47','San Sebastián de Buenavista'),
 ('47703','47','San Zenón'),
 ('47707','47','Santa Ana'),
 ('47720','47','Santa Bárbara de Pinto'),
 ('47745','47','Sitionuevo'),
 ('47798','47','Tenerife'),
 ('47960','47','Zapayán'),
 ('47980','47','Zona Bananera'),
 ('50001','50','Villavicencio'),
 ('50006','50','Acacías'),
 ('50110','50','Barranca de Upía'),
 ('50124','50','Cabuyaro'),
 ('50150','50','Castilla la Nueva'),
 ('50223','50','Cubarral'),
 ('50226','50','Cumaral'),
 ('50245','50','El Calvario'),
 ('50251','50','El Castillo'),
 ('50270','50','El Dorado'),
 ('50287','50','Fuente de Oro'),
 ('50313','50','Granada'),
 ('50318','50','Guamal'),
 ('50325','50','Mapiripán'),
 ('50330','50','Mesetas'),
 ('50350','50','La Macarena'),
 ('50370','50','Uribe'),
 ('50400','50','Lejanías'),
 ('50450','50','Puerto Concordia'),
 ('50568','50','Puerto Gaitán'),
 ('50573','50','Puerto López'),
 ('50577','50','Puerto Lleras'),
 ('50590','50','Puerto Rico'),
 ('50606','50','Restrepo'),
 ('50680','50','San Carlos de Guaroa'),
 ('50683','50','San Juan de Arama'),
 ('50686','50','San Juanito'),
 ('50689','50','San Martín'),
 ('50711','50','Vistahermosa'),
 ('52001','52','Pasto'),
 ('52019','52','Albán'),
 ('52022','52','Aldana'),
 ('52036','52','Ancuya'),
 ('52051','52','Arboleda'),
 ('52079','52','Barbacoas'),
 ('52083','52','Belén'),
 ('52110','52','Buesaco'),
 ('52203','52','Colón'),
 ('52207','52','Consacá'),
 ('52210','52','Contadero'),
 ('52215','52','Córdoba'),
 ('52224','52','Cuaspud Carlosama'),
 ('52227','52','Cumbal'),
 ('52233','52','Cumbitara'),
 ('52240','52','Chachagüí'),
 ('52250','52','El Charco'),
 ('52254','52','El Peñol'),
 ('52256','52','El Rosario'),
 ('52258','52','El Tablón de Gómez'),
 ('52260','52','El Tambo'),
 ('52287','52','Funes'),
 ('52317','52','Guachucal'),
 ('52320','52','Guaitarilla'),
 ('52323','52','Gualmatán'),
 ('52352','52','Iles'),
 ('52354','52','Imués'),
 ('52356','52','Ipiales'),
 ('52378','52','La Cruz'),
 ('52381','52','La Florida'),
 ('52385','52','La Llanada'),
 ('52390','52','La Tola'),
 ('52399','52','La Unión'),
 ('52405','52','Leiva'),
 ('52411','52','Linares'),
 ('52418','52','Los Andes'),
 ('52427','52','Magüí'),
 ('52435','52','Mallama'),
 ('52473','52','Mosquera'),
 ('52480','52','Nariño'),
 ('52490','52','Olaya Herrera'),
 ('52506','52','Ospina'),
 ('52520','52','Francisco Pizarro'),
 ('52540','52','Policarpa'),
 ('52560','52','Potosí'),
 ('52565','52','Providencia'),
 ('52573','52','Puerres'),
 ('52585','52','Pupiales'),
 ('52612','52','Ricaurte'),
 ('52621','52','Roberto Payán'),
 ('52678','52','Samaniego'),
 ('52683','52','Sandoná'),
 ('52685','52','San Bernardo'),
 ('52687','52','San Lorenzo'),
 ('52693','52','San Pablo'),
 ('52694','52','San Pedro de Cartago'),
 ('52696','52','Santa Bárbara'),
 ('52699','52','Santacruz'),
 ('52720','52','Sapuyes'),
 ('52786','52','Taminango'),
 ('52788','52','Tangua'),
 ('52835','52','San Andrés de Tumaco'),
 ('52838','52','Túquerres'),
 ('52885','52','Yacuanquer'),
 ('54001','54','San José de Cúcuta'),
 ('54003','54','Ábrego'),
 ('54051','54','Arboledas'),
 ('54099','54','Bochalema'),
 ('54109','54','Bucarasica'),
 ('54125','54','Cácota'),
 ('54128','54','Cáchira'),
 ('54172','54','Chinácota'),
 ('54174','54','Chitagá'),
 ('54206','54','Convención'),
 ('54223','54','Cucutilla'),
 ('54239','54','Durania'),
 ('54245','54','El Carmen'),
 ('54250','54','El Tarra'),
 ('54261','54','El Zulia'),
 ('54313','54','Gramalote'),
 ('54344','54','Hacarí'),
 ('54347','54','Herrán'),
 ('54377','54','Labateca'),
 ('54385','54','La Esperanza'),
 ('54398','54','La Playa'),
 ('54405','54','Los Patios'),
 ('54418','54','Lourdes'),
 ('54480','54','Mutiscua'),
 ('54498','54','Ocaña'),
 ('54518','54','Pamplona'),
 ('54520','54','Pamplonita'),
 ('54553','54','Puerto Santander'),
 ('54599','54','Ragonvalia'),
 ('54660','54','Salazar'),
 ('54670','54','San Calixto'),
 ('54673','54','San Cayetano'),
 ('54680','54','Santiago'),
 ('54720','54','Sardinata'),
 ('54743','54','Silos'),
 ('54800','54','Teorama'),
 ('54810','54','Tibú'),
 ('54820','54','Toledo'),
 ('54871','54','Villa Caro'),
 ('54874','54','Villa del Rosario'),
 ('63001','63','Armenia'),
 ('63111','63','Buenavista'),
 ('63130','63','Calarcá'),
 ('63190','63','Circasia'),
 ('63212','63','Córdoba'),
 ('63272','63','Filandia'),
 ('63302','63','Génova'),
 ('63401','63','La Tebaida'),
 ('63470','63','Montenegro'),
 ('63548','63','Pijao'),
 ('63594','63','Quimbaya'),
 ('63690','63','Salento'),
 ('66001','66','Pereira'),
 ('66045','66','Apía'),
 ('66075','66','Balboa'),
 ('66088','66','Belén de Umbría'),
 ('66170','66','Dosquebradas'),
 ('66318','66','Guática'),
 ('66383','66','La Celia'),
 ('66400','66','La Virginia'),
 ('66440','66','Marsella'),
 ('66456','66','Mistrató'),
 ('66572','66','Pueblo Rico'),
 ('66594','66','Quinchía'),
 ('66682','66','Santa Rosa de Cabal'),
 ('66687','66','Santuario'),
 ('68001','68','Bucaramanga'),
 ('68013','68','Aguada'),
 ('68020','68','Albania'),
 ('68051','68','Aratoca'),
 ('68077','68','Barbosa'),
 ('68079','68','Barichara'),
 ('68081','68','Barrancabermeja'),
 ('68092','68','Betulia'),
 ('68101','68','Bolívar'),
 ('68121','68','Cabrera'),
 ('68132','68','California'),
 ('68147','68','Capitanejo'),
 ('68152','68','Carcasí'),
 ('68160','68','Cepitá'),
 ('68162','68','Cerrito'),
 ('68167','68','Charalá'),
 ('68169','68','Charta'),
 ('68176','68','Chima'),
 ('68179','68','Chipatá'),
 ('68190','68','Cimitarra'),
 ('68207','68','Concepción'),
 ('68209','68','Confines'),
 ('68211','68','Contratación'),
 ('68217','68','Coromoro'),
 ('68229','68','Curití'),
 ('68235','68','El Carmen de Chucurí'),
 ('68245','68','El Guacamayo'),
 ('68250','68','El Peñón'),
 ('68255','68','El Playón'),
 ('68264','68','Encino'),
 ('68266','68','Enciso'),
 ('68271','68','Florián'),
 ('68276','68','Floridablanca'),
 ('68296','68','Galán'),
 ('68298','68','Gámbita'),
 ('68307','68','Girón'),
 ('68318','68','Guaca'),
 ('68320','68','Guadalupe'),
 ('68322','68','Guapotá'),
 ('68324','68','Guavatá'),
 ('68327','68','Güepsa'),
 ('68344','68','Hato'),
 ('68368','68','Jesús María'),
 ('68370','68','Jordán'),
 ('68377','68','La Belleza'),
 ('68385','68','Landázuri'),
 ('68397','68','La Paz'),
 ('68406','68','Lebrija'),
 ('68418','68','Los Santos'),
 ('68425','68','Macaravita'),
 ('68432','68','Málaga'),
 ('68444','68','Matanza'),
 ('68464','68','Mogotes'),
 ('68468','68','Molagavita'),
 ('68498','68','Ocamonte'),
 ('68500','68','Oiba'),
 ('68502','68','Onzaga'),
 ('68522','68','Palmar'),
 ('68524','68','Palmas del Socorro'),
 ('68533','68','Páramo'),
 ('68547','68','Piedecuesta'),
 ('68549','68','Pinchote'),
 ('68572','68','Puente Nacional'),
 ('68573','68','Puerto Parra'),
 ('68575','68','Puerto Wilches'),
 ('68615','68','Rionegro'),
 ('68655','68','Sabana de Torres'),
 ('68669','68','San Andrés'),
 ('68673','68','San Benito'),
 ('68679','68','San Gil'),
 ('68682','68','San Joaquín'),
 ('68684','68','San José de Miranda'),
 ('68686','68','San Miguel'),
 ('68689','68','San Vicente de Chucurí'),
 ('68705','68','Santa Bárbara'),
 ('68720','68','Santa Helena del Opón'),
 ('68745','68','Simacota'),
 ('68755','68','Socorro'),
 ('68770','68','Suaita'),
 ('68773','68','Sucre'),
 ('68780','68','Suratá'),
 ('68820','68','Tona'),
 ('68855','68','Valle de San José'),
 ('68861','68','Vélez'),
 ('68867','68','Vetas'),
 ('68872','68','Villanueva'),
 ('68895','68','Zapatoca'),
 ('70001','70','Sincelejo'),
 ('70110','70','Buenavista'),
 ('70124','70','Caimito'),
 ('70204','70','Colosó'),
 ('70215','70','Corozal'),
 ('70221','70','Coveñas'),
 ('70230','70','Chalán'),
 ('70233','70','El Roble'),
 ('70235','70','Galeras'),
 ('70265','70','Guaranda'),
 ('70400','70','La Unión'),
 ('70418','70','Los Palmitos'),
 ('70429','70','Majagual'),
 ('70473','70','Morroa'),
 ('70508','70','Ovejas'),
 ('70523','70','Palmito'),
 ('70670','70','Sampués'),
 ('70678','70','San Benito Abad'),
 ('70702','70','San Juan de Betulia'),
 ('70708','70','San Marcos'),
 ('70713','70','San Onofre'),
 ('70717','70','San Pedro'),
 ('70742','70','San Luis de Sincé'),
 ('70771','70','Sucre'),
 ('70820','70','Santiago de Tolú'),
 ('70823','70','San José de Toluviejo'),
 ('73001','73','Ibagué'),
 ('73024','73','Alpujarra'),
 ('73026','73','Alvarado'),
 ('73030','73','Ambalema'),
 ('73043','73','Anzoátegui'),
 ('73055','73','Armero'),
 ('73067','73','Ataco'),
 ('73124','73','Cajamarca'),
 ('73148','73','Carmen de Apicalá'),
 ('73152','73','Casabianca'),
 ('73168','73','Chaparral'),
 ('73200','73','Coello'),
 ('73217','73','Coyaima'),
 ('73226','73','Cunday'),
 ('73236','73','Dolores'),
 ('73268','73','Espinal'),
 ('73270','73','Falan'),
 ('73275','73','Flandes'),
 ('73283','73','Fresno'),
 ('73319','73','Guamo'),
 ('73347','73','Herveo'),
 ('73349','73','Honda'),
 ('73352','73','Icononzo'),
 ('73408','73','Lérida'),
 ('73411','73','Líbano'),
 ('73443','73','San Sebastián de Mariquita'),
 ('73449','73','Melgar'),
 ('73461','73','Murillo'),
 ('73483','73','Natagaima'),
 ('73504','73','Ortega'),
 ('73520','73','Palocabildo'),
 ('73547','73','Piedras'),
 ('73555','73','Planadas'),
 ('73563','73','Prado'),
 ('73585','73','Purificación'),
 ('73616','73','Rioblanco'),
 ('73622','73','Roncesvalles'),
 ('73624','73','Rovira'),
 ('73671','73','Saldaña'),
 ('73675','73','San Antonio'),
 ('73678','73','San Luis'),
 ('73686','73','Santa Isabel'),
 ('73770','73','Suárez'),
 ('73854','73','Valle de San Juan'),
 ('73861','73','Venadillo'),
 ('73870','73','Villahermosa'),
 ('73873','73','Villarrica'),
 ('76001','76','Santiago de Cali'),
 ('76020','76','Alcalá'),
 ('76036','76','Andalucía'),
 ('76041','76','Ansermanuevo'),
 ('76054','76','Argelia'),
 ('76100','76','Bolívar'),
 ('76109','76','Buenaventura'),
 ('76111','76','Guadalajara de Buga'),
 ('76113','76','Bugalagrande'),
 ('76122','76','Caicedonia'),
 ('76126','76','Calima'),
 ('76130','76','Candelaria'),
 ('76147','76','Cartago'),
 ('76233','76','Dagua'),
 ('76243','76','El Águila'),
 ('76246','76','El Cairo'),
 ('76248','76','El Cerrito'),
 ('76250','76','El Dovio'),
 ('76275','76','Florida'),
 ('76306','76','Ginebra'),
 ('76318','76','Guacarí'),
 ('76364','76','Jamundí'),
 ('76377','76','La Cumbre'),
 ('76400','76','La Unión'),
 ('76403','76','La Victoria'),
 ('76497','76','Obando'),
 ('76520','76','Palmira'),
 ('76563','76','Pradera'),
 ('76606','76','Restrepo'),
 ('76616','76','Riofrío'),
 ('76622','76','Roldanillo'),
 ('76670','76','San Pedro'),
 ('76736','76','Sevilla'),
 ('76823','76','Toro'),
 ('76828','76','Trujillo'),
 ('76834','76','Tuluá'),
 ('76845','76','Ulloa'),
 ('76863','76','Versalles'),
 ('76869','76','Vijes'),
 ('76890','76','Yotoco'),
 ('76892','76','Yumbo'),
 ('76895','76','Zarzal'),
 ('81001','81','Arauca'),
 ('81065','81','Arauquita'),
 ('81220','81','Cravo Norte'),
 ('81300','81','Fortul'),
 ('81591','81','Puerto Rondón'),
 ('81736','81','Saravena'),
 ('81794','81','Tame'),
 ('85001','85','Yopal'),
 ('85010','85','Aguazul'),
 ('85015','85','Chámeza'),
 ('85125','85','Hato Corozal'),
 ('85136','85','La Salina'),
 ('85139','85','Maní'),
 ('85162','85','Monterrey'),
 ('85225','85','Nunchía'),
 ('85230','85','Orocué'),
 ('85250','85','Paz de Ariporo'),
 ('85263','85','Pore'),
 ('85279','85','Recetor'),
 ('85300','85','Sabanalarga'),
 ('85315','85','Sácama'),
 ('85325','85','San Luis de Palenque'),
 ('85400','85','Támara'),
 ('85410','85','Tauramena'),
 ('85430','85','Trinidad'),
 ('85440','85','Villanueva'),
 ('86001','86','Mocoa'),
 ('86219','86','Colón'),
 ('86320','86','Orito'),
 ('86568','86','Puerto Asís'),
 ('86569','86','Puerto Caicedo'),
 ('86571','86','Puerto Guzmán'),
 ('86573','86','Puerto Leguízamo'),
 ('86749','86','Sibundoy'),
 ('86755','86','San Francisco'),
 ('86757','86','San Miguel'),
 ('86760','86','Santiago'),
 ('86865','86','Valle del Guamuez'),
 ('86885','86','Villagarzón'),
 ('88001','88','San Andrés'),
 ('88564','88','Providencia'),
 ('91001','91','Leticia'),
 ('91263','91','El Encanto'),
 ('91405','91','La Chorrera'),
 ('91407','91','La Pedrera'),
 ('91430','91','La Victoria'),
 ('91460','91','Mirití - Paraná'),
 ('91530','91','Puerto Alegría'),
 ('91536','91','Puerto Arica'),
 ('91540','91','Puerto Nariño'),
 ('91669','91','Puerto Santander'),
 ('91798','91','Tarapacá'),
 ('94001','94','Inírida'),
 ('94343','94','Barrancominas'),
 ('94883','94','San Felipe'),
 ('94884','94','Puerto Colombia'),
 ('94885','94','La Guadalupe'),
 ('94886','94','Cacahual'),
 ('94887','94','Pana Pana'),
 ('94888','94','Morichal'),
 ('95001','95','San José del Guaviare'),
 ('95015','95','Calamar'),
 ('95025','95','El Retorno'),
 ('95200','95','Miraflores'),
 ('97001','97','Mitú'),
 ('97161','97','Carurú'),
 ('97511','97','Pacoa'),
 ('97666','97','Taraira'),
 ('97777','97','Papunahua'),
 ('97889','97','Yavaraté'),
 ('99001','99','Puerto Carreño'),
 ('99524','99','La Primavera'),
 ('99624','99','Santa Rosalía'),
 ('99773','99','Cumaribo')
ON CONFLICT (cod_dane) DO UPDATE SET cod_dpto=excluded.cod_dpto, nombre=excluded.nombre;


-- ======================= 012_aps.sql =======================
-- =====================================================================
--  012_aps.sql — Área de Prestación del Servicio (APS).
--
--  Captura los criterios regulatorios para el establecimiento del APS del
--  art. 2.1.2.1.1.5 de la Res. CRA 1032 de 2026. Se establece UN APS por cada
--  municipio/distrito que atiende la empresa (un registro por empresa_id +
--  cod_dane, apoyado en empresa_municipio de la migración 010).
--
--  Además, aps_archivo guarda los soportes que la 1032 exige o sugiere por APS
--  (mapa y coordenadas georreferenciadas, instrumento de ordenamiento, Plan
--  Maestro, reporte al municipio, etc.) en los formatos Excel/CSV/PDF e imágenes
--  o archivos geográficos del polígono. Rol dueño (postgres).
-- =====================================================================

-- ---------- APS (un registro por municipio del prestador) ----------
CREATE TABLE IF NOT EXISTS aps (
  id             serial PRIMARY KEY,
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  cod_dane       char(5) REFERENCES municipio(cod_dane),   -- municipio/distrito del APS (DIVIPOLA)
  numero_aps     smallint,                                 -- número/identificador del APS en la empresa
  nombre         text,                                     -- rótulo del APS (p. ej. «APS Neiva»)
  codigo_aps     text,                                     -- código propio / id del APS en el SUI (si aplica)

  -- Servicios que presta en el municipio (art. 2.1.2.1.1.5)
  servicios              text NOT NULL DEFAULT 'ambos',    -- ac | al | ambos
  aps_difiere_servicios  boolean NOT NULL DEFAULT false,   -- APS distinta por servicio (solo uno / fuentes alternas / criterios ambientales)

  -- Zonas de prestación
  zona           text NOT NULL DEFAULT 'urbana',           -- urbana | urbana_rural
  sistema_rural  text NOT NULL DEFAULT 'na',               -- na | integrado | no_integrado_urbana | no_integrado_urbano_rural

  -- Configuración regional (esquemas que atienden dos o más municipios)
  esquema_regional        boolean NOT NULL DEFAULT false,
  sistema_interconexion   text NOT NULL DEFAULT 'na',      -- na | interconectado | no_interconectado | mixto
  tipo_regional           text NOT NULL DEFAULT 'na',      -- na | mercado_regional | costos_unificados | no_unificados
  mercado_regional_declarado boolean NOT NULL DEFAULT false,

  -- Condiciones especiales / APS de menor tamaño (art. 2.1.2.1.1.5 y condición especial)
  aplicaba_825   boolean NOT NULL DEFAULT false,           -- le resultaba aplicable la Res. CRA 825 de 2017
  menor_5000     boolean NOT NULL DEFAULT false,           -- APS con 5.000 suscriptores o menos
  pdet           boolean NOT NULL DEFAULT false,           -- municipio PDET (Decreto Ley 893 de 2017)
  zomac          boolean NOT NULL DEFAULT false,           -- ZOMAC (art. 236 Ley 1819 de 2016)
  ed_particular  boolean NOT NULL DEFAULT false,           -- esquema diferencial de prestación en condición particular
  ed_urbano_zdu  boolean NOT NULL DEFAULT false,           -- esquema diferencial urbano (ZDU, área de difícil gestión)
  ed_rural_zrni  boolean NOT NULL DEFAULT false,           -- zona rural con sistema no integrado (ZRNI)
  toma_posesion_sspd boolean NOT NULL DEFAULT false,       -- en toma de posesión por la SSPD

  -- Georreferenciación (se mantiene de la Res. CRA 688; MAGNA-SIRGAS)
  georref_sistema    text NOT NULL DEFAULT 'MAGNA-SIRGAS',
  georref_presentada boolean NOT NULL DEFAULT false,       -- se adjuntó mapa + polígono + listado de coordenadas
  area_ha            numeric(14,2),                        -- área del APS en hectáreas (opcional)

  -- Ordenamiento del territorio y reporte al municipio
  instrumento_ot      text,                                -- POT | PBOT | EOT
  instrumento_ot_acto text,                                -- acto que lo adopta (acuerdo/decreto n.º y año)
  pmaa                boolean NOT NULL DEFAULT false,       -- cuenta con Plan Maestro de Acueducto y Alcantarillado
  reportado_municipio boolean NOT NULL DEFAULT false,      -- APS reportada al municipio/distrito
  reportado_fecha     date,
  reportado_acto      text,

  observacion     text,
  actualizado_por integer REFERENCES usuario(id),
  creado_en       timestamptz NOT NULL DEFAULT now(),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, cod_dane),
  CHECK (servicios     IN ('ac','al','ambos')),
  CHECK (zona          IN ('urbana','urbana_rural')),
  CHECK (sistema_rural IN ('na','integrado','no_integrado_urbana','no_integrado_urbano_rural')),
  CHECK (sistema_interconexion IN ('na','interconectado','no_interconectado','mixto')),
  CHECK (tipo_regional IN ('na','mercado_regional','costos_unificados','no_unificados')),
  CHECK (instrumento_ot IS NULL OR instrumento_ot IN ('POT','PBOT','EOT'))
);
CREATE INDEX IF NOT EXISTS ix_aps_emp ON aps(empresa_id);

-- ---------- Soportes documentales por APS (Excel/CSV/PDF/imagen/geo) ----------
CREATE TABLE IF NOT EXISTS aps_archivo (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  aps_id      integer NOT NULL REFERENCES aps(id) ON DELETE CASCADE,
  categoria   text NOT NULL,            -- georreferenciacion | pot_pbot_eot | pmaa | reporte_municipio | soporte_825 | soporte_general
  nombre      text NOT NULL,            -- nombre original del archivo
  tipo        text,                     -- extensión/tipo (pdf, xlsx, csv, png, kml…)
  tamano      integer,                  -- tamaño en bytes
  contenido   bytea NOT NULL,           -- contenido del archivo
  subido_por  integer REFERENCES usuario(id),
  subido_en   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_apsarch_emp ON aps_archivo(empresa_id);
CREATE INDEX IF NOT EXISTS ix_apsarch_aps ON aps_archivo(aps_id);

-- ---------- RLS por empresa ----------
ALTER TABLE aps         ENABLE ROW LEVEL SECURITY;
ALTER TABLE aps_archivo ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS aps_all ON aps;
CREATE POLICY aps_all ON aps FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS apsarch_all ON aps_archivo;
CREATE POLICY apsarch_all ON aps_archivo FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON aps, aps_archivo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE aps_id_seq, aps_archivo_id_seq TO app_user;


-- ======================= 013_cargue_bcr.sql =======================
-- =====================================================================
--  013_cargue_bcr.sql — Costos particulares (1032) e inventario de la BCR.
--
--  · costo_particular: costos particulares que reconoce la metodología, por año
--    y servicio (insumo del menú «Cargar información», pestaña Costos particulares).
--  · bcr_activo: inventario activo-por-activo de la Base de Capital Regulada, por
--    los tres componentes del art. 2.1.2.1.3.5.18 (1-infraestructura,
--    2-inversiones ambientales y de gestión del riesgo, 3-activos administrativos
--    y operativos). Alimenta el CMI_BCR y la proyección del CMI. Rol dueño (postgres).
-- =====================================================================

-- ---------- Costos particulares (Res. CRA 1032) ----------
CREATE TABLE IF NOT EXISTS costo_particular (
  id          serial PRIMARY KEY,
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  anio        smallint NOT NULL,                 -- año al que corresponde (→ año tarifario)
  servicio    text NOT NULL DEFAULT 'acueducto', -- acueducto | alcantarillado | general
  categoria   text,                              -- agrupador (p. ej. CMO, CMA, tasas, contratos)
  concepto    text NOT NULL,                     -- descripción del costo particular
  valor       double precision,                  -- valor ($)
  unidad      text,                              -- $/mes, $/m³, $ total…
  soporte     text,                              -- referencia del soporte
  origen      text NOT NULL DEFAULT 'empresa',   -- empresa | SUI | supuesto
  observacion text,
  cargado_por integer REFERENCES usuario(id),
  cargado_en  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, anio, servicio, concepto),
  CHECK (servicio IN ('acueducto','alcantarillado','general'))
);
CREATE INDEX IF NOT EXISTS ix_cpart_emp ON costo_particular(empresa_id);

-- ---------- Inventario de activos de la BCR ----------
CREATE TABLE IF NOT EXISTS bcr_activo (
  id              serial PRIMARY KEY,
  empresa_id      integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio        text NOT NULL,                 -- acueducto | alcantarillado
  componente      smallint NOT NULL,             -- 1 infraestructura | 2 ambiental/riesgo | 3 admin/operativo
  nombre          text NOT NULL,                 -- nombre del activo
  cod_dane        char(5) REFERENCES municipio(cod_dane),  -- APS (opcional)
  valor_bruto     double precision,              -- valor del activo (pesos dic i-1)
  plazo_remanente numeric(6,2),                  -- años de recuperación remanente
  cuota_anual     double precision,              -- cuota anual de recuperación del capital (cak, art. 2.1.2.1.3.5.11)
  valor_pendiente double precision,              -- valor pendiente por recuperar (integra la BCR)
  origen          text NOT NULL DEFAULT 'BCR0',  -- BCR0_688 | BCR0_825 | POIR | nuevo
  observacion     text,
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now(),
  actualizado_en  timestamptz NOT NULL DEFAULT now(),
  CHECK (servicio IN ('acueducto','alcantarillado')),
  CHECK (componente IN (1,2,3))
);
CREATE INDEX IF NOT EXISTS ix_bcr_emp ON bcr_activo(empresa_id);
CREATE INDEX IF NOT EXISTS ix_bcr_emp_serv ON bcr_activo(empresa_id, servicio);

-- ---------- RLS por empresa ----------
ALTER TABLE costo_particular ENABLE ROW LEVEL SECURITY;
ALTER TABLE bcr_activo       ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cpart_all ON costo_particular;
CREATE POLICY cpart_all ON costo_particular FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS bcr_all ON bcr_activo;
CREATE POLICY bcr_all ON bcr_activo FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON costo_particular, bcr_activo TO app_user;
GRANT USAGE, SELECT ON SEQUENCE costo_particular_id_seq, bcr_activo_id_seq TO app_user;


-- ======================= 014_bcr0_inicio.sql =======================
-- =====================================================================
--  014_bcr0_inicio.sql — Reconstrucción de la BCR₀ de inicio de la 1032.
--
--  Núcleo de variables para calcular la BCR₀ a partir del marco anterior
--  (Res. 688/825): parámetros de reconstrucción por servicio (bcr_param),
--  series de agua facturada y CMI cobrado por año tarifario de la 688
--  (bcr_serie) y las variables de la cadena del VA₀ por activo
--  (ampliación de bcr_activo). Arts. 2.1.2.1.3.5.3 a .7, .11, .13, .18 y
--  2.1.2.1.5.2.1.1. Rol dueño (postgres).
-- =====================================================================

-- ---------- Parámetros de reconstrucción 688 por servicio ----------
CREATE TABLE IF NOT EXISTS bcr_param (
  empresa_id       integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio         text NOT NULL,
  r688             double precision,          -- tasa de descuento de la Res. 688
  ipc_dic_2014     double precision,          -- IPC dic-2014 (para fa0)
  ipc_dic_2025     double precision,          -- IPC dic-2025 (para fa0)
  fecha_inicio_688 date,                       -- inicio de aplicación de la 688 (→ t a 30-jun-2026)
  provision_poir   double precision,          -- saldo provisión POIR no ejecutado (Res. 950, 30-jun-2026)
  ccp_2025         double precision,          -- CCP 2025 (m³/año) para dividir el CI → CMI_BCR
  observacion      text,
  actualizado_en   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (empresa_id, servicio),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- Series por año tarifario de la 688 (agua facturada y CMI cobrado) ----------
CREATE TABLE IF NOT EXISTS bcr_serie (
  empresa_id     integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio       text NOT NULL,
  anio_tarifario smallint NOT NULL,           -- 1..10 de aplicación de la 688
  q_m3           double precision,            -- agua facturada en el año (m³)
  cmi_cobrado    double precision,            -- CMI688 efectivamente cobrado ($/m³)
  PRIMARY KEY (empresa_id, servicio, anio_tarifario),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- Variables de la cadena del VA₀ por activo ----------
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS tipo_activo     text;        -- subsistema/actividad/tipo
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vida_util       numeric(6,2);-- VU
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS via688          double precision;  -- VIA688ⱼ ($dic-2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vp_cmi_q        double precision;  -- VP(CMI688×Q) recuperado
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS vpr0            double precision;  -- VPR₀ = VIA − VP(CMI×Q) ($dic-2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS va0             double precision;  -- VA₀ ($dic-2025) antes de compensar
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS anio_poir       smallint;    -- año tarifario de entrada en operación (POIR)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS ejecucion_real  double precision;  -- valor ejecutado real POIR ($2014)
ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS fecha_operacion date;        -- fecha real de operación (POIR)

-- ---------- RLS ----------
ALTER TABLE bcr_param ENABLE ROW LEVEL SECURITY;
ALTER TABLE bcr_serie ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS bcrparam_all ON bcr_param;
CREATE POLICY bcrparam_all ON bcr_param FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS bcrserie_all ON bcr_serie;
CREATE POLICY bcrserie_all ON bcr_serie FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON bcr_param, bcr_serie TO app_user;


-- ======================= 015_poir_cmi.sql =======================
-- =====================================================================
--  015_poir_cmi.sql — Ingresos por proyecto: CMI por activo y modificaciones del POIR.
--
--  El cálculo de los ingresos recuperados vía CMI (VP(CMI688ⱼ×Qt)) es
--  ACTIVO POR ACTIVO (art. 2.1.2.1.3.5.5). El CMI de la 688 pudo modificarse
--  durante su aplicación (modificaciones del POIR), de modo que un mismo activo
--  puede tener distintos CMI según el período. Se capturan:
--   · poir_modificacion — cuántas modificaciones y en qué fechas (0 = POIR original);
--   · activo_cmi — el CMI de cada activo bajo cada modificación (de un Excel por modificación);
--   · bcr_activo.codigo — identificador del activo/proyecto para enlazar.
--  Rol dueño (postgres).
-- =====================================================================

ALTER TABLE bcr_activo ADD COLUMN IF NOT EXISTS codigo text;   -- identificador del activo/proyecto
CREATE INDEX IF NOT EXISTS ix_bcr_cod ON bcr_activo(empresa_id, servicio, codigo);

-- ---------- Modificaciones del POIR (0 = original) ----------
CREATE TABLE IF NOT EXISTS poir_modificacion (
  empresa_id  integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio    text NOT NULL,
  numero      smallint NOT NULL,          -- 0 = POIR original; 1..N = modificaciones
  fecha       date,                        -- fecha de entrada en vigencia de la modificación
  descripcion text,
  PRIMARY KEY (empresa_id, servicio, numero),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);

-- ---------- CMI por activo bajo cada modificación ----------
CREATE TABLE IF NOT EXISTS activo_cmi (
  empresa_id   integer NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
  servicio     text NOT NULL,
  codigo       text NOT NULL,              -- identificador del activo/proyecto
  modificacion smallint NOT NULL,          -- 0..N (enlaza con poir_modificacion.numero)
  cmi          double precision,           -- CMI688 del activo bajo esa modificación ($/m³)
  PRIMARY KEY (empresa_id, servicio, codigo, modificacion),
  CHECK (servicio IN ('acueducto','alcantarillado'))
);
CREATE INDEX IF NOT EXISTS ix_acmi_cod ON activo_cmi(empresa_id, servicio, codigo);

-- ---------- RLS ----------
ALTER TABLE poir_modificacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE activo_cmi        ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS poirmod_all ON poir_modificacion;
CREATE POLICY poirmod_all ON poir_modificacion FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

DROP POLICY IF EXISTS acmi_all ON activo_cmi;
CREATE POLICY acmi_all ON activo_cmi FOR ALL
  USING      (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

-- ---------- Grants ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON poir_modificacion, activo_cmi TO app_user;


-- ======================= 016_costos_particulares_coc.sql =======================
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


-- ======================= 017_ccp_fap.sql =======================
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

