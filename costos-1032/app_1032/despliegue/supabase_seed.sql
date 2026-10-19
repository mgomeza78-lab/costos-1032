-- =====================================================================
-- supabase_seed.sql — DATOS de ejemplo (3 empresas, usuarios, parámetros,
-- operación y recálculo ilustrativos). Ejecútelo DESPUÉS de supabase_setup.sql.
-- Usuarios: la clave de todos es la de la semilla (cámbiela al entrar).
-- =====================================================================
--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)


--
-- Data for Name: segmento; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.segmento (id, nombre, susc_min, susc_max, r, kct, ipuf_estrella, articulo_r, articulo_kct) VALUES (1, 'Primer segmento (> 300.000 suscriptores)', 300001, NULL, 0.08580, 0.01780, 6.00, '2.1.2.1.3.1.7', '2.1.2.1.3.1.8');
INSERT INTO public.segmento (id, nombre, susc_min, susc_max, r, kct, ipuf_estrella, articulo_r, articulo_kct) VALUES (2, 'Segundo segmento (90.000 – 300.000 suscriptores)', 90000, 300000, 0.09030, 0.01540, 6.00, '2.1.2.1.3.1.7', '2.1.2.1.3.1.8');


--
-- Data for Name: empresa; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.empresa (id, codigo, nombre, nit, municipio, segmento_id, presta_ac, presta_al, esquema, r, kct, fecha_inicio_688, fecha_inicio_1032, aplicacion_1032_tardia, creado_en) VALUES (1, 'LAS_CEIBAS', 'Las Ceibas E.P. de Neiva E.S.P.', NULL, 'Neiva (Huila)', 2, true, true, 'por servicio', 0.09030, 0.01540, NULL, '2026-07-01', false, '2026-10-16 13:51:22.432744+00');
INSERT INTO public.empresa (id, codigo, nombre, nit, municipio, segmento_id, presta_ac, presta_al, esquema, r, kct, fecha_inicio_688, fecha_inicio_1032, aplicacion_1032_tardia, creado_en) VALUES (2, 'ESSMAR', 'ESSMAR E.S.P.', NULL, 'Santa Marta (Magdalena)', 2, true, true, 'por servicio', 0.09030, 0.01540, '2019-05-31', NULL, true, '2026-10-16 13:51:22.432744+00');
INSERT INTO public.empresa (id, codigo, nombre, nit, municipio, segmento_id, presta_ac, presta_al, esquema, r, kct, fecha_inicio_688, fecha_inicio_1032, aplicacion_1032_tardia, creado_en) VALUES (3, 'AMB', 'Acueducto Metropolitano de Bucaramanga S.A. E.S.P.', NULL, 'Área Metropolitana de Bucaramanga (Santander)', 1, true, false, 'por confirmar (posible esquema regional metropolitano)', 0.08580, 0.01780, '2016-07-01', '2026-07-01', false, '2026-10-16 13:51:22.432744+00');


--
-- Data for Name: rol; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.rol (id, codigo, nombre) VALUES (1, 'admin', 'Administrador');
INSERT INTO public.rol (id, codigo, nombre) VALUES (2, 'analista', 'Analista');
INSERT INTO public.rol (id, codigo, nombre) VALUES (3, 'empresa', 'Empresa');
INSERT INTO public.rol (id, codigo, nombre) VALUES (4, 'auditor', 'Auditor (solo lectura)');


--
-- Data for Name: usuario; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (3, 'operador.neiva@lasceibas.gov.co', 'Operador Las Ceibas', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 3, 1, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, NULL);
INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (5, 'operador@amb.com.co', 'Operador amb', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 3, 3, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, NULL);
INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (6, 'auditor@sspd.gov.co', 'Auditor (muestra)', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 4, 1, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, '2026-10-16 17:59:04.958262+00');
INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (1, 'mgomeza78@gmail.com', 'Mauro Gómez (consultor)', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 1, NULL, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, '2026-10-16 17:59:08.477373+00');
INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (4, 'operador@essmar.gov.co', 'Operador ESSMAR', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 3, 2, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, '2026-10-16 17:59:08.898028+00');
INSERT INTO public.usuario (id, email, nombre, password_hash, rol_id, empresa_id, activo, creado_en, intentos_fallidos, bloqueado_hasta, mfa_secret, mfa_activo, debe_cambiar_pass, ultimo_login) VALUES (2, 'analista@sictaa.co', 'Analista SICTAA', '$2b$12$keVucw/.ZyjqtpXrQsOKjel8esvsPQ4hAx..BPXIaqrXKEaSKbqKO', 2, NULL, true, '2026-10-16 13:51:22.432744+00', 0, NULL, NULL, false, false, '2026-10-16 17:59:00.766985+00');


--
-- Data for Name: proyecto_inversion; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.proyecto_inversion (id, empresa_id, codigo_poir, nombre, servicio, aps, componente_sistema, meta_asociada, clasificacion, origen, valor_planeado, fecha_planeada_operacion, fecha_real_operacion, estado, via688, vp_recaudo, vida_util, observacion, creado_por, creado_en, actualizado_en) VALUES (1, 1, 'POIR-AC-001', 'Ampliación PTAP El Jardín', 'acueducto', 'Neiva', 'tratamiento', 'continuidad y calidad (IRCA)', 'CMI_POIR', 'POIR_688', 15000000000, '2026-11-30', NULL, 'en_ejecucion', 9800000000, 7200000000, 25.00, NULL, NULL, '2026-10-16 17:52:20.142847+00', '2026-10-16 17:52:20.142847+00');
INSERT INTO public.proyecto_inversion (id, empresa_id, codigo_poir, nombre, servicio, aps, componente_sistema, meta_asociada, clasificacion, origen, valor_planeado, fecha_planeada_operacion, fecha_real_operacion, estado, via688, vp_recaudo, vida_util, observacion, creado_por, creado_en, actualizado_en) VALUES (2, 1, 'POIR-AC-002', 'Renovación de redes de distribución Comuna 6', 'acueducto', 'Neiva', 'distribución', 'reducción de pérdidas (IANC)', 'CMI_POIR', 'POIR_nuevo', 8000000000, '2026-12-31', NULL, 'en_ejecucion', NULL, NULL, 30.00, NULL, NULL, '2026-10-16 17:52:20.142847+00', '2026-10-16 17:52:20.142847+00');
INSERT INTO public.proyecto_inversion (id, empresa_id, codigo_poir, nombre, servicio, aps, componente_sistema, meta_asociada, clasificacion, origen, valor_planeado, fecha_planeada_operacion, fecha_real_operacion, estado, via688, vp_recaudo, vida_util, observacion, creado_por, creado_en, actualizado_en) VALUES (3, 1, 'POIR-AL-001', 'Reposición colector principal', 'alcantarillado', 'Neiva', 'recolección', 'cobertura de alcantarillado', 'expost_general', 'POIR_nuevo', 5000000000, '2026-10-31', '2026-09-20', 'en_operacion', NULL, NULL, 40.00, NULL, NULL, '2026-10-16 17:52:20.142847+00', '2026-10-16 17:52:20.142847+00');
INSERT INTO public.proyecto_inversion (id, empresa_id, codigo_poir, nombre, servicio, aps, componente_sistema, meta_asociada, clasificacion, origen, valor_planeado, fecha_planeada_operacion, fecha_real_operacion, estado, via688, vp_recaudo, vida_util, observacion, creado_por, creado_en, actualizado_en) VALUES (4, 1, 'POIR-AC-003', 'Macromedición y sectorización (DMA)', 'acueducto', 'Neiva', 'macromedición', 'reducción de pérdidas (IANC)', 'expost_general', 'POIR_nuevo', 1200000000, '2026-12-15', NULL, 'en_ejecucion', NULL, NULL, 15.00, NULL, NULL, '2026-10-16 17:52:20.142847+00', '2026-10-16 17:52:20.142847+00');


--
-- Data for Name: avance_inversion; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (1, 1, 1, 2026, 7, 60, 9000000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (2, 1, 1, 2026, 9, 85, 12750000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (3, 1, 2, 2026, 7, 25, 2000000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (4, 1, 2, 2026, 9, 45, 3600000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (5, 1, 3, 2026, 7, 70, 3500000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (6, 1, 3, 2026, 9, 100, 5000000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');
INSERT INTO public.avance_inversion (id, empresa_id, proyecto_id, anio, mes, avance_fisico, avance_financiero, observacion, cargado_por, cargado_en) VALUES (7, 1, 4, 2026, 7, 40, 480000000, NULL, NULL, '2026-10-16 17:52:20.142847+00');


--
-- Data for Name: base_calculo; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (1, 1, 'acueducto', 'CACe', 20160534251, '$/año', '2.1.2.1.3.2.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (2, 1, 'acueducto', 'COCe', 18627211481, '$/año', '2.1.2.1.3.4.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (3, 1, 'acueducto', 'CE', 389844472, '$/año', '2.1.2.1.3.4.6', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (4, 1, 'acueducto', 'CIQ', 5931959600, '$/año', '2.1.2.1.3.4.7', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (5, 1, 'acueducto', 'COIR', 0, '$/año', '2.1.2.1.3.4.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (6, 1, 'acueducto', 'ICTA', 3700269413.18479, '$/año', '2.1.2.1.3.6.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (7, 1, 'acueducto', 'ITO', 0, '$/año', '2.1.2.1.3.6.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (8, 1, 'acueducto', 'TA', 0, '$/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (9, 1, 'acueducto', 'N', 132987.08, 'suscriptores', '2.1.2.1.3.2.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (10, 1, 'acueducto', 'CCP', 36831353, 'm³/año', '2.1.2.1.3.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (11, 1, 'acueducto', 'AF', 36831353, 'm³/año', '2.1.2.1.3.3', 'supuesto', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (12, 1, 'acueducto', 'denom_cmict', 36831353, 'm³/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (13, 1, 'acueducto', 'Fa_cma', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (14, 1, 'acueducto', 'Fa_cmo', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (15, 1, 'acueducto', 'Fa_cmict', 1.0187, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (16, 1, 'acueducto', 'kct', 0.0154, 'factor', '2.1.2.1.3.1.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (17, 1, 'acueducto', 'CMI_base', 832.06, '$/m³', '2.1.2.1.3.5', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (18, 1, 'alcantarillado', 'CACe', 15645169196, '$/año', '2.1.2.1.3.2.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (19, 1, 'alcantarillado', 'COCe', 3289403325, '$/año', '2.1.2.1.3.4.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (20, 1, 'alcantarillado', 'CE', 0, '$/año', '2.1.2.1.3.4.6', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (21, 1, 'alcantarillado', 'CIQ', 0, '$/año', '2.1.2.1.3.4.7', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (22, 1, 'alcantarillado', 'COIR', 0, '$/año', '2.1.2.1.3.4.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (23, 1, 'alcantarillado', 'ICTA', 3861849913.9945536, '$/año', '2.1.2.1.3.6.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (24, 1, 'alcantarillado', 'ITO', 0, '$/año', '2.1.2.1.3.6.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (25, 1, 'alcantarillado', 'TA', 0, '$/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (26, 1, 'alcantarillado', 'N', 129075.58, 'suscriptores', '2.1.2.1.3.2.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (27, 1, 'alcantarillado', 'CCP', 35720101, 'm³/año', '2.1.2.1.3.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (28, 1, 'alcantarillado', 'AF', 20708404, 'm³/año', '2.1.2.1.3.3', 'supuesto', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (29, 1, 'alcantarillado', 'denom_cmict', 20708404, 'm³/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (30, 1, 'alcantarillado', 'Fa_cma', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (31, 1, 'alcantarillado', 'Fa_cmo', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (32, 1, 'alcantarillado', 'Fa_cmict', 1.0187, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (33, 1, 'alcantarillado', 'kct', 0.0154, 'factor', '2.1.2.1.3.1.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (34, 1, 'alcantarillado', 'CMI_base', 1267.04, '$/m³', '2.1.2.1.3.5', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (35, 2, 'acueducto', 'CACe', 10639001426.16, '$/año', '2.1.2.1.3.2.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (36, 2, 'acueducto', 'COCe', 18117293825.32, '$/año', '2.1.2.1.3.4.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (37, 2, 'acueducto', 'CE', 3576220648.28, '$/año', '2.1.2.1.3.4.6', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (38, 2, 'acueducto', 'CIQ', 3395217675.43, '$/año', '2.1.2.1.3.4.7', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (39, 2, 'acueducto', 'COIR', 0, '$/año', '2.1.2.1.3.4.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (40, 2, 'acueducto', 'ICTA', 2358827081.58, '$/año', '2.1.2.1.3.6.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (41, 2, 'acueducto', 'ITO', 146527444.65, '$/año', '2.1.2.1.3.6.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (42, 2, 'acueducto', 'TA', 116907443.7, '$/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (43, 2, 'acueducto', 'N', 124847.33, 'suscriptores', '2.1.2.1.3.2.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (44, 2, 'acueducto', 'CCP', 25603905.2, 'm³/año', '2.1.2.1.3.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (45, 2, 'acueducto', 'AF', 25603905.2, 'm³/año', '2.1.2.1.3.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (46, 2, 'acueducto', 'denom_cmict', 28736405.8, 'm³/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (47, 2, 'acueducto', 'Fa_cma', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (48, 2, 'acueducto', 'Fa_cmo', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (49, 2, 'acueducto', 'Fa_cmict', 1.0187, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (50, 2, 'acueducto', 'kct', 0.0154, 'factor', '2.1.2.1.3.1.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (51, 2, 'acueducto', 'CMI_base', 1584.71, '$/m³', '2.1.2.1.3.5', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (52, 2, 'alcantarillado', 'CACe', 6706770944.89, '$/año', '2.1.2.1.3.2.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (53, 2, 'alcantarillado', 'COCe', 12383336135.19, '$/año', '2.1.2.1.3.4.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (54, 2, 'alcantarillado', 'CE', 2341463396.52, '$/año', '2.1.2.1.3.4.6', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (55, 2, 'alcantarillado', 'CIQ', 0, '$/año', '2.1.2.1.3.4.7', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (56, 2, 'alcantarillado', 'COIR', 0, '$/año', '2.1.2.1.3.4.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (57, 2, 'alcantarillado', 'ICTA', 2080026072.11, '$/año', '2.1.2.1.3.6.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (58, 2, 'alcantarillado', 'ITO', 560715179.65, '$/año', '2.1.2.1.3.6.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (59, 2, 'alcantarillado', 'TA', 2859238324.4, '$/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (60, 2, 'alcantarillado', 'N', 118665, 'suscriptores', '2.1.2.1.3.2.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (61, 2, 'alcantarillado', 'CCP', 23653949.77, 'm³/año', '2.1.2.1.3.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (62, 2, 'alcantarillado', 'AF', 12966468, 'm³/año', '2.1.2.1.3.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (63, 2, 'alcantarillado', 'denom_cmict', 12966468, 'm³/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (64, 2, 'alcantarillado', 'Fa_cma', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (65, 2, 'alcantarillado', 'Fa_cmo', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (66, 2, 'alcantarillado', 'Fa_cmict', 1.0187, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (67, 2, 'alcantarillado', 'kct', 0.0154, 'factor', '2.1.2.1.3.1.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (68, 2, 'alcantarillado', 'CMI_base', 1904.48, '$/m³', '2.1.2.1.3.5', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (69, 3, 'acueducto', 'CACe', 32074141441.62, '$/año', '2.1.2.1.3.2.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (70, 3, 'acueducto', 'COCe', 90193116804.59, '$/año', '2.1.2.1.3.4.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (71, 3, 'acueducto', 'CE', 16556091865.36, '$/año', '2.1.2.1.3.4.6', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (72, 3, 'acueducto', 'CIQ', 3954096154.82, '$/año', '2.1.2.1.3.4.7', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (73, 3, 'acueducto', 'COIR', 0, '$/año', '2.1.2.1.3.4.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (74, 3, 'acueducto', 'ICTA', 2468873438.72, '$/año', '2.1.2.1.3.6.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (75, 3, 'acueducto', 'ITO', 2387708741.25, '$/año', '2.1.2.1.3.6.4', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (76, 3, 'acueducto', 'TA', 387455138, '$/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (77, 3, 'acueducto', 'N', 322007.83, 'suscriptores', '2.1.2.1.3.2.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (78, 3, 'acueducto', 'CCP', 51468023, 'm³/año', '2.1.2.1.3.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (79, 3, 'acueducto', 'AF', 51468023, 'm³/año', '2.1.2.1.3.3', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (80, 3, 'acueducto', 'denom_cmict', 53545833, 'm³/año', '2.1.2.1.3.6.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (81, 3, 'acueducto', 'Fa_cma', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (82, 3, 'acueducto', 'Fa_cmo', 1.06727106506171, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (83, 3, 'acueducto', 'Fa_cmict', 1.0187, 'factor', '2.1.2.1.5.3.1', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (84, 3, 'acueducto', 'kct', 0.0178, 'factor', '2.1.2.1.3.1.8', 'validada', '2026-10-16 17:38:35.403053+00');
INSERT INTO public.base_calculo (id, empresa_id, servicio, clave, valor, unidad, articulo, procedencia, actualizado_en) VALUES (85, 3, 'acueducto', 'CMI_base', 2297.37, '$/m³', '2.1.2.1.3.5', 'validada', '2026-10-16 17:38:35.403053+00');


--
-- Data for Name: carga_mensual; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (53, 1, 2026, 7, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (54, 1, 2026, 7, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (55, 1, 2026, 8, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (56, 1, 2026, 8, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (57, 1, 2026, 9, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (58, 1, 2026, 9, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (59, 1, 2026, 10, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (60, 1, 2026, 10, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (61, 1, 2026, 11, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (62, 1, 2026, 11, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (63, 1, 2026, 12, 'acueducto', 112000, 1950000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (64, 1, 2026, 12, 'alcantarillado', 108500, 1780000, 'muestra', NULL, '2026-10-16 15:31:22.794021+00', NULL, NULL);
INSERT INTO public.carga_mensual (id, empresa_id, anio, mes, servicio, suscriptores, m3_facturados, origen, cargado_por, cargado_en, facturacion, novedades) VALUES (65, 2, 2026, 8, 'acueducto', 95000, 1500000, 'archivo_propio', 4, '2026-10-16 17:59:02.344381+00', NULL, 'prueba');


--
-- Data for Name: carga_mensual_detalle; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (97, 1, 2026, 7, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (98, 1, 2026, 7, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (99, 1, 2026, 7, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (100, 1, 2026, 7, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (101, 1, 2026, 7, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (102, 1, 2026, 7, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (103, 1, 2026, 8, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (104, 1, 2026, 8, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (105, 1, 2026, 8, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (106, 1, 2026, 8, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (107, 1, 2026, 8, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (108, 1, 2026, 8, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (109, 1, 2026, 9, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (110, 1, 2026, 9, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (111, 1, 2026, 9, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (112, 1, 2026, 9, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (113, 1, 2026, 9, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (114, 1, 2026, 9, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (115, 1, 2026, 10, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (116, 1, 2026, 10, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (117, 1, 2026, 10, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (118, 1, 2026, 10, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (119, 1, 2026, 10, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (120, 1, 2026, 10, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (121, 1, 2026, 11, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (122, 1, 2026, 11, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (123, 1, 2026, 11, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (124, 1, 2026, 11, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (125, 1, 2026, 11, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (126, 1, 2026, 11, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (127, 1, 2026, 12, 'acueducto', 1, 32739, 350910, 303641, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (128, 1, 2026, 12, 'acueducto', 2, 63322, 702709, 598234, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (129, 1, 2026, 12, 'acueducto', 3, 16227, 175998, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (130, 1, 2026, 12, 'acueducto', 5, 2600, 65000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (131, 1, 2026, 12, 'acueducto', 6, 1500, 48000, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (132, 1, 2026, 12, 'acueducto', 11, 5800, 120400, 0, 'muestra', NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (133, 2, 2026, 7, 'acueducto', 1, 20000, 210000, 180000, 'SUI', NULL, '2026-10-16 15:31:32.885818+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (134, 2, 2026, 7, 'acueducto', 10, 3000, 70000, 0, 'SUI', NULL, '2026-10-16 15:31:32.885818+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (135, 2, 2026, 8, 'acueducto', 1, 2, 22, 17, 'SUI', NULL, '2026-10-16 15:31:33.335941+00');
INSERT INTO public.carga_mensual_detalle (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, origen, cargado_por, cargado_en) VALUES (136, 2, 2026, 8, 'acueducto', 11, 1, 50, 0, 'SUI', NULL, '2026-10-16 15:31:33.335941+00');


--
-- Data for Name: costo_referencia_mensual; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (7, 2, 2026, 7, 'acueducto', 23000, 280000, 0, 0, NULL, 280000, 41773.77079128085, 8091.915369381567, 1584.71, 719.2734453227662, 280000, 41773.77079128085, 8091.915369381567, 1584.71, 719.2734453227662, 7695.77, 2741, 41773.77079128085, 10395.898814704333, -34078.00079128085, -7654.898814704333, 'prorrateo_base', '2026-10-16 17:38:36.043677+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (8, 2, 2026, 8, 'acueducto', 3, 72, 0, 0, NULL, 72, 320265576.06648654, 31468559.769817203, 1584.71, 2797174.509588535, 280072, 83536.64549836627, 16179.670252126873, 1584.71, 1438.1770736837277, 7695.77, 2741, 320265576.06648654, 34267318.98940574, -320257880.29648656, -34264577.98940574, 'prorrateo_base', '2026-10-16 17:38:36.043677+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (1, 1, 2026, 7, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 5992.587865187174, 525.4948779793855, 832.06, 119.85382946790756, 2196145, 5992.587865187174, 525.4948779793855, 832.06, 119.85382946790756, 13690.62, 1670.0700000000002, 5992.587865187174, 1477.408707447293, 7698.032134812826, 192.6612925527072, 'balance', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (2, 1, 2026, 8, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 14900.612776457137, 1025.9425714329143, 832.06, 145.23609187007233, 4392290, 10446.600320822157, 775.7187247061498, 832.06, 132.54496066898994, 13690.62, 1670.0700000000002, 14900.612776457137, 2003.2386633029867, -1209.9927764571366, -333.1686633029865, 'prorrateo_base', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (3, 1, 2026, 9, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 14900.612776457137, 1025.9425714329143, 832.06, 145.23609187007233, 6588435, 11931.27113936715, 859.1266736150712, 832.06, 136.7753377360174, 13690.62, 1670.0700000000002, 14900.612776457137, 2003.2386633029867, -1209.9927764571366, -333.1686633029865, 'prorrateo_base', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (4, 1, 2026, 10, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 14900.612776457137, 1025.9425714329143, 832.06, 145.23609187007233, 8784580, 12673.60654863965, 900.8306480695321, 832.06, 138.8905262695312, 13690.62, 1670.0700000000002, 14900.612776457137, 2003.2386633029867, -1209.9927764571366, -333.1686633029865, 'prorrateo_base', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (5, 1, 2026, 11, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 14900.612776457137, 1025.9425714329143, 832.06, 145.23609187007233, 10980725, 13119.007794203148, 925.8530327422087, 832.06, 140.15963938963938, 14115.02922, 1721.8421699999997, 14900.612776457137, 2003.2386633029867, -785.5835564571371, -281.396493302987, 'prorrateo_base', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (6, 1, 2026, 12, 'acueducto', 122188, 1463017, 2200000, 736983, 33.499227272727275, 2196145, 14900.612776457137, 1025.9425714329143, 832.06, 145.23609187007233, 13176870, 13415.941957912146, 942.534622523993, 832.06, 141.00571480304487, 14115.02922, 1721.8421699999997, 14900.612776457137, 2003.2386633029867, -785.5835564571371, -281.396493302987, 'prorrateo_base', '2026-10-16 17:59:06.654962+00');
INSERT INTO public.costo_referencia_mensual (id, empresa_id, anio, mes, servicio, n_mes, af_mes, ap_mes, perdidas_mes, ianc, ccp_mes, cma_mes, cmo_mes, cmi_mes, cmict_mes, ccp_acum, cma_acum, cmo_acum, cmi_acum, cmict_acum, cobrado_cf, cobrado_cc, ref_cf, ref_cc, brecha_cf, brecha_cc, origen_numerador, calculado_en) VALUES (21, 1, 2026, 7, 'alcantarillado', 0, 0, 0, 0, NULL, 0, NULL, NULL, 1267.04, NULL, 0, NULL, NULL, 1267.04, NULL, 10946.29, 1559.74, NULL, 1267.04, NULL, 292.70000000000005, 'balance', '2026-10-16 17:59:06.654962+00');


--
-- Data for Name: factor_subsidio; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (37, 1, 2026, 'acueducto', 1, -0.7, -0.7, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (38, 1, 2026, 'acueducto', 2, -0.4, -0.4, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (39, 1, 2026, 'acueducto', 3, -0.15, -0.15, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (40, 1, 2026, 'acueducto', 5, 0.5, 0.5, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (41, 1, 2026, 'acueducto', 6, 0.6, 0.6, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (42, 1, 2026, 'acueducto', 11, 0.5, 0.5, NULL, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (44, 2, 2026, 'acueducto', 10, 0.5, 0.5, NULL, '2026-10-16 15:31:32.918816+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (43, 2, 2026, 'acueducto', 1, 0, -0.54, NULL, '2026-10-16 15:31:32.918816+00');
INSERT INTO public.factor_subsidio (id, empresa_id, vigencia, servicio, clase, factor_cargofijo, factor_consumo, cargado_por, cargado_en) VALUES (46, 2, 2026, 'acueducto', 11, 1, 0.6, NULL, '2026-10-16 15:31:33.335941+00');


--
-- Data for Name: factura_clase; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (81, 1, 2026, 7, 'acueducto', 1, 32739, 350910, 303641, 134465162.45400003, 231073056.29100004, -668723253.135, 365538218.74500006, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (82, 1, 2026, 7, 'acueducto', 2, 63322, 702709, 598234, 520150463.78400004, 773936157.0780001, -746404038.4080001, 1294086620.862, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (83, 1, 2026, 7, 'acueducto', 3, 16227, 175998, 0, 188834037.129, 293928979.86, -33323653.611, 482763016.989, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (84, 1, 2026, 7, 'acueducto', 5, 2600, 65000, 0, 53393418, 108554550.00000001, 17797806, 161947968, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (85, 1, 2026, 7, 'acueducto', 6, 1500, 48000, 0, 32857488, 80163360.00000001, 12321558, 113020848.00000001, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (86, 1, 2026, 7, 'acueducto', 11, 5800, 120400, 0, 119108394, 201076428.00000003, 39702798, 320184822, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (87, 1, 2026, 8, 'acueducto', 1, 32739, 350910, 303641, 134465162.45400003, 231073056.29100004, -668723253.135, 365538218.74500006, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (88, 1, 2026, 8, 'acueducto', 2, 63322, 702709, 598234, 520150463.78400004, 773936157.0780001, -746404038.4080001, 1294086620.862, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (89, 1, 2026, 8, 'acueducto', 3, 16227, 175998, 0, 188834037.129, 293928979.86, -33323653.611, 482763016.989, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (90, 1, 2026, 8, 'acueducto', 5, 2600, 65000, 0, 53393418, 108554550.00000001, 17797806, 161947968, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (91, 1, 2026, 8, 'acueducto', 6, 1500, 48000, 0, 32857488, 80163360.00000001, 12321558, 113020848.00000001, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (92, 1, 2026, 8, 'acueducto', 11, 5800, 120400, 0, 119108394, 201076428.00000003, 39702798, 320184822, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (93, 1, 2026, 9, 'acueducto', 1, 32739, 350910, 303641, 134465162.45400003, 231073056.29100004, -668723253.135, 365538218.74500006, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (94, 1, 2026, 9, 'acueducto', 2, 63322, 702709, 598234, 520150463.78400004, 773936157.0780001, -746404038.4080001, 1294086620.862, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (95, 1, 2026, 9, 'acueducto', 3, 16227, 175998, 0, 188834037.129, 293928979.86, -33323653.611, 482763016.989, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (96, 1, 2026, 9, 'acueducto', 5, 2600, 65000, 0, 53393418, 108554550.00000001, 17797806, 161947968, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (97, 1, 2026, 9, 'acueducto', 6, 1500, 48000, 0, 32857488, 80163360.00000001, 12321558, 113020848.00000001, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (98, 1, 2026, 9, 'acueducto', 11, 5800, 120400, 0, 119108394, 201076428.00000003, 39702798, 320184822, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (99, 1, 2026, 10, 'acueducto', 1, 32739, 350910, 303641, 134465162.45400003, 231073056.29100004, -668723253.135, 365538218.74500006, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (100, 1, 2026, 10, 'acueducto', 2, 63322, 702709, 598234, 520150463.78400004, 773936157.0780001, -746404038.4080001, 1294086620.862, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (101, 1, 2026, 10, 'acueducto', 3, 16227, 175998, 0, 188834037.129, 293928979.86, -33323653.611, 482763016.989, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (102, 1, 2026, 10, 'acueducto', 5, 2600, 65000, 0, 53393418, 108554550.00000001, 17797806, 161947968, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (103, 1, 2026, 10, 'acueducto', 6, 1500, 48000, 0, 32857488, 80163360.00000001, 12321558, 113020848.00000001, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (104, 1, 2026, 10, 'acueducto', 11, 5800, 120400, 0, 119108394, 201076428.00000003, 39702798, 320184822, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (105, 1, 2026, 11, 'acueducto', 1, 32739, 350910, 303641, 138633582.49007404, 238236321.036021, -689453673.9821849, 376869903.52609503, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (106, 1, 2026, 11, 'acueducto', 2, 63322, 702709, 598234, 536275128.161304, 797928177.9474177, -769542563.5986481, 1334203306.1087217, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (107, 1, 2026, 11, 'acueducto', 3, 16227, 175998, 0, 194687892.279999, 303040778.23565996, -34356686.872941, 497728670.515659, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (108, 1, 2026, 11, 'acueducto', 5, 2600, 65000, 0, 55048613.958000004, 111919741.04999998, 18349537.986, 166968355.008, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (109, 1, 2026, 11, 'acueducto', 6, 1500, 48000, 0, 33876070.128000006, 82648424.15999998, 12703526.298, 116524494.28799999, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (110, 1, 2026, 11, 'acueducto', 11, 5800, 120400, 0, 122800754.21399999, 207309797.26799995, 40933584.738, 330110551.48199993, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (111, 1, 2026, 12, 'acueducto', 1, 32739, 350910, 303641, 138633582.49007404, 238236321.036021, -689453673.9821849, 376869903.52609503, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (112, 1, 2026, 12, 'acueducto', 2, 63322, 702709, 598234, 536275128.161304, 797928177.9474177, -769542563.5986481, 1334203306.1087217, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (113, 1, 2026, 12, 'acueducto', 3, 16227, 175998, 0, 194687892.279999, 303040778.23565996, -34356686.872941, 497728670.515659, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (114, 1, 2026, 12, 'acueducto', 5, 2600, 65000, 0, 55048613.958000004, 111919741.04999998, 18349537.986, 166968355.008, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (115, 1, 2026, 12, 'acueducto', 6, 1500, 48000, 0, 33876070.128000006, 82648424.15999998, 12703526.298, 116524494.28799999, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (116, 1, 2026, 12, 'acueducto', 11, 5800, 120400, 0, 122800754.21399999, 207309797.26799995, 40933584.738, 330110551.48199993, '2026-10-16 15:31:22.794021+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (117, 2, 2026, 7, 'acueducto', 1, 20000, 210000, 180000, 153915400, 309184800, -266425200.00000003, 463100200, '2026-10-16 17:59:05.000789+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (118, 2, 2026, 7, 'acueducto', 10, 3000, 70000, 0, 34630965, 191870000, 11543655, 226500965, '2026-10-16 17:59:05.000789+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (123, 2, 2026, 8, 'acueducto', 1, 2, 22, 17, 15391.54, 35139.62, -25162.38, 50531.16, '2026-10-16 17:59:05.000789+00');
INSERT INTO public.factura_clase (id, empresa_id, anio, mes, servicio, clase, suscriptores, m3, m3_subsidiable, cf_facturado, cc_facturado, subsidio_contribucion, factura_total, calculado_en) VALUES (124, 2, 2026, 8, 'acueducto', 11, 1, 50, 0, 15391.54, 137050, 7695.77, 152441.54, '2026-10-16 17:59:05.000789+00');


--
-- Data for Name: indicador_mensual; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: indice_ipc; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 7, 100.000000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 100.000000);
INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 8, 100.800000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 100.800000);
INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 9, 101.500000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 101.500000);
INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 10, 102.300000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 102.300000);
INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 11, 103.100000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 103.100000);
INSERT INTO public.indice_ipc (anio, mes, indice, fuente, procedencia, cargado_por, cargado_en, ipcs) VALUES (2026, 12, 103.700000, 'DANE (ilustrativo)', 'supuesto', NULL, '2026-10-16 15:31:22.794021+00', 103.700000);


--
-- Data for Name: macromedicion; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (1, 1, 2026, 7, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');
INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (2, 1, 2026, 8, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');
INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (3, 1, 2026, 9, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');
INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (4, 1, 2026, 10, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');
INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (5, 1, 2026, 11, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');
INSERT INTO public.macromedicion (id, empresa_id, anio, mes, servicio, punto, m3_producido, m3_bloque_entregado, m3_bloque_recibido, origen, cargado_por, cargado_en) VALUES (6, 1, 2026, 12, 'acueducto', 'PTAP El Jardín (muestra)', 2200000, NULL, NULL, 'propio', NULL, '2026-10-16 17:38:35.403053+00');


--
-- Data for Name: numerador_mensual; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (1, 1, 2026, 7, 'acueducto', 'CACe', 675664454.8824524, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (2, 1, 2026, 7, 'alcantarillado', 'CACe', 524335545.1175477, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (3, 1, 2026, 7, 'acueducto', 'COCe', 764921521.014754, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (4, 1, 2026, 7, 'alcantarillado', 'COCe', 135078478.98524588, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (5, 1, 2026, 7, 'acueducto', 'CE', 300000000, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (6, 1, 2026, 7, 'alcantarillado', 'CE', 0, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (7, 1, 2026, 7, 'acueducto', 'ICTA', 24465822.695269365, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (8, 1, 2026, 7, 'alcantarillado', 'ICTA', 25534177.30473063, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (9, 1, 2026, 7, 'acueducto', 'ITO', 150000000, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (10, 1, 2026, 7, 'alcantarillado', 'ITO', 0, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (11, 1, 2026, 7, 'acueducto', 'TA', 80000000, 'balance', NULL, '2026-10-16 17:43:40.078095+00');
INSERT INTO public.numerador_mensual (id, empresa_id, anio, mes, servicio, concepto, valor, origen, cargado_por, cargado_en) VALUES (12, 1, 2026, 7, 'alcantarillado', 'TA', 0, 'balance', NULL, '2026-10-16 17:43:40.078095+00');


--
-- Data for Name: resultado_componente; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (1, 1, 'acueducto', 'CMO', 734.09, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.4.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (2, 1, 'acueducto', 'CMI', 832.06, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.5.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (3, 1, 'acueducto', 'CMICT', 103.92, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.6.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (4, 1, 'acueducto', 'CMA', 13690.62, '$/susc·mes', 'validada', 'núcleo numerador por servicio', '2.1.2.1.3.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (5, 1, 'acueducto', 'BCR0', 207518425294, '$', 'validada', 'núcleo bcr0_cmi vs modelo 06_BCR0', '2.1.2.1.3.5.4.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (6, 1, 'acueducto', 'CARGO_FIJO', 13690.62, '$/susc·mes', 'validada', '= CMA', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (7, 1, 'acueducto', 'CARGO_CONSUMO', 1670.07, '$/m³', 'calculada', '= CMO + CMI + CMICT', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (8, 1, 'alcantarillado', 'CMO', 99.8, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.4.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (9, 1, 'alcantarillado', 'CMI', 1267.04, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.5.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (10, 1, 'alcantarillado', 'CMICT', 192.9, '$/m³', 'validada', 'motor_1032 reconciliado vs modelo v69 (07_Validacion)', '2.1.2.1.3.6.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (11, 1, 'alcantarillado', 'CMA', 10946.29, '$/susc·mes', 'validada', 'núcleo numerador por servicio', '2.1.2.1.3.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (12, 1, 'alcantarillado', 'BCR0', 291752478328, '$', 'validada', 'núcleo bcr0_cmi vs modelo 06_BCR0', '2.1.2.1.3.5.4.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (13, 1, 'alcantarillado', 'CARGO_FIJO', 10946.29, '$/susc·mes', 'validada', '= CMA', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (14, 1, 'alcantarillado', 'CARGO_CONSUMO', 1559.74, '$/m³', 'calculada', '= CMO + CMI + CMICT', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (15, 2, 'acueducto', 'CMA', 7695.77, '$/susc·mes', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (16, 2, 'acueducto', 'CMO', 1061.9, '$/m³', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.4.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (17, 2, 'acueducto', 'CMI', 1584.71, '$/m³', 'validada', 'núcleo bcr0_cmi vs 17_BCR0 (CMI_BCR dic-2025); radicado indexado ×faep0', '2.1.2.1.3.5.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (18, 2, 'acueducto', 'CMICT', 94.39, '$/m³', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.6.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (19, 2, 'acueducto', 'FACTURA', 35098.66, '$/mes', 'radicada', 'Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025 (indexado ×faep0)', '', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (20, 2, 'acueducto', 'BCR0', 339104000000, '$', 'radicada', 'Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025', '2.1.2.1.3.5.4.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (21, 2, 'acueducto', 'CARGO_FIJO', 7695.77, '$/susc·mes', 'validada', '= CMA', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (22, 2, 'acueducto', 'CARGO_CONSUMO', 2741, '$/m³', 'calculada', '= CMO + CMI + CMICT', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (23, 2, 'alcantarillado', 'CMA', 5104.13, '$/susc·mes', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (24, 2, 'alcantarillado', 'CMO', 674.62, '$/m³', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.4.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (25, 2, 'alcantarillado', 'CMI', 1904.48, '$/m³', 'validada', 'núcleo bcr0_cmi vs 17_BCR0 (CMI_BCR dic-2025); radicado indexado ×faep0', '2.1.2.1.3.5.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (26, 2, 'alcantarillado', 'CMICT', 438.75, '$/m³', 'validada', 'núcleo componentes vs modelo ESSMAR 08/09/20 (dic-2025); radicado = ×faep0', '2.1.2.1.3.6.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (27, 2, 'alcantarillado', 'FACTURA', 33404.17, '$/mes', 'radicada', 'Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025 (indexado ×faep0)', '', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (28, 2, 'alcantarillado', 'BCR0', 330604000000, '$', 'radicada', 'Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025', '2.1.2.1.3.5.4.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (29, 2, 'alcantarillado', 'CARGO_FIJO', 5104.13, '$/susc·mes', 'validada', '= CMA', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (30, 2, 'alcantarillado', 'CARGO_CONSUMO', 3017.85, '$/m³', 'calculada', '= CMO + CMI + CMICT', '2.1.2.1.2.1.', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (31, 2, '—', 'FACTURA_CONJUNTA', 68502.83, '$/mes', 'radicada', 'Radicación ESSMAR (LÉAME radicación CRA), pesos dic-2025 (indexado ×faep0)', '', '2026-10-16 13:51:22.432744+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (32, 3, 'acueducto', 'CMA', 9016.64, '$/susc·mes', 'validada', 'núcleo componentes vs modelo amb VF (dic-2025)', '2.1.2.1.3.2.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (33, 3, 'acueducto', 'CMO', 2336.47, '$/m³', 'validada', 'núcleo componentes vs modelo amb VF (dic-2025)', '2.1.2.1.3.4.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (34, 3, 'acueducto', 'CMI', 2297.37, '$/m³', 'validada', 'núcleo bcr0_cmi vs Formato_BCR0_amb_diligenciado (2.666 activos); reproduce al peso', '2.1.2.1.3.5.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (35, 3, 'acueducto', 'CMICT', 101.68, '$/m³', 'validada', 'núcleo (reproduce el modelo); incluye doble conteo del impuesto de vehículos $7,2M — limpio 101,54 (hallazgo CMICT!D33)', '2.1.2.1.3.6.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (36, 3, 'acueducto', 'BCR0', 1080558309074, '$', 'validada', 'núcleo bcr0_cmi vs Formato_BCR0_amb_diligenciado (2.666 activos); reproduce al peso', '2.1.2.1.3.5.4.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (37, 3, 'acueducto', 'CARGO_FIJO', 9016.64, '$/susc·mes', 'validada', '= CMA', '2.1.2.1.2.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (38, 3, 'acueducto', 'CARGO_CONSUMO', 4735.5199999999995, '$/m³', 'calculada', '= CMO + CMI + CMICT', '2.1.2.1.2.1.', '2026-10-16 17:58:57.307041+00');
INSERT INTO public.resultado_componente (id, empresa_id, servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en) VALUES (39, 3, '—', 'COC', 85094645944, '$', 'validada', 'COCe del CMO (hoja 05a); reproducido dentro del CMO 2.336,47', '', '2026-10-16 17:58:57.307041+00');


--
-- Data for Name: tarifa_vigente; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (146, 1, 2026, 8, 'acueducto', 13690.62, 1670.0700000000002, 1, 0.008000000000000007, false, '2026-10-16 15:31:22.794021+00', 0.008000000000000007, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (147, 1, 2026, 9, 'acueducto', 13690.62, 1670.0700000000002, 1, 0.014999999999999902, false, '2026-10-16 15:31:22.794021+00', 0.014999999999999902, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (148, 1, 2026, 10, 'acueducto', 13690.62, 1670.0700000000002, 1, 0.02299999999999991, false, '2026-10-16 15:31:22.794021+00', 0.02299999999999991, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (149, 1, 2026, 11, 'acueducto', 14115.02922, 1721.8421699999997, 1.031, 0.030999999999999917, true, '2026-10-16 15:31:22.794021+00', 0.030999999999999917, true);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (150, 1, 2026, 12, 'acueducto', 14115.02922, 1721.8421699999997, 1.031, 0.005819592628516057, false, '2026-10-16 15:31:22.794021+00', 0.005819592628516057, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (151, 1, 2026, 7, 'alcantarillado', 10946.29, 1559.74, 1, 0, false, '2026-10-16 15:31:22.794021+00', 0, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (152, 1, 2026, 8, 'alcantarillado', 10946.29, 1559.74, 1, 0.008000000000000007, false, '2026-10-16 15:31:22.794021+00', 0.008000000000000007, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (153, 1, 2026, 9, 'alcantarillado', 10946.29, 1559.74, 1, 0.014999999999999902, false, '2026-10-16 15:31:22.794021+00', 0.014999999999999902, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (154, 1, 2026, 10, 'alcantarillado', 10946.29, 1559.74, 1, 0.02299999999999991, false, '2026-10-16 15:31:22.794021+00', 0.02299999999999991, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (155, 1, 2026, 11, 'alcantarillado', 11285.62499, 1608.0919399999998, 1.031, 0.030999999999999917, true, '2026-10-16 15:31:22.794021+00', 0.030999999999999917, true);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (156, 1, 2026, 12, 'alcantarillado', 11285.62499, 1608.0919399999998, 1.031, 0.005819592628516057, false, '2026-10-16 15:31:22.794021+00', 0.005819592628516057, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (157, 2, 2026, 7, 'acueducto', 7695.77, 2741, 1, 0, false, '2026-10-16 17:59:02.996818+00', 0, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (158, 2, 2026, 8, 'acueducto', 7695.77, 2741, 1, 0.008000000000000007, false, '2026-10-16 17:59:02.996818+00', 0.008000000000000007, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (159, 2, 2026, 9, 'acueducto', 7695.77, 2741, 1, 0.014999999999999902, false, '2026-10-16 17:59:02.996818+00', 0.014999999999999902, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (160, 2, 2026, 10, 'acueducto', 7695.77, 2741, 1, 0.02299999999999991, false, '2026-10-16 17:59:02.996818+00', 0.02299999999999991, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (161, 2, 2026, 11, 'acueducto', 7934.33887, 2825.971, 1.031, 0.030999999999999917, true, '2026-10-16 17:59:02.996818+00', 0.030999999999999917, true);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (162, 2, 2026, 12, 'acueducto', 7934.33887, 2825.971, 1.031, 0.005819592628516057, false, '2026-10-16 17:59:02.996818+00', 0.005819592628516057, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (163, 2, 2026, 7, 'alcantarillado', 5104.13, 3017.85, 1, 0, false, '2026-10-16 17:59:02.996818+00', 0, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (164, 2, 2026, 8, 'alcantarillado', 5104.13, 3017.85, 1, 0.008000000000000007, false, '2026-10-16 17:59:02.996818+00', 0.008000000000000007, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (165, 2, 2026, 9, 'alcantarillado', 5104.13, 3017.85, 1, 0.014999999999999902, false, '2026-10-16 17:59:02.996818+00', 0.014999999999999902, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (166, 2, 2026, 10, 'alcantarillado', 5104.13, 3017.85, 1, 0.02299999999999991, false, '2026-10-16 17:59:02.996818+00', 0.02299999999999991, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (167, 2, 2026, 11, 'alcantarillado', 5262.358029999999, 3111.4033499999996, 1.031, 0.030999999999999917, true, '2026-10-16 17:59:02.996818+00', 0.030999999999999917, true);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (168, 2, 2026, 12, 'alcantarillado', 5262.358029999999, 3111.4033499999996, 1.031, 0.005819592628516057, false, '2026-10-16 17:59:02.996818+00', 0.005819592628516057, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (145, 1, 2026, 7, 'acueducto', 13690.62, 1670.0700000000002, 1, 0, false, '2026-10-16 15:31:22.794021+00', 0, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (169, 3, 2026, 7, 'acueducto', 9016.64, 4735.52, 1, 0, false, '2026-10-16 15:31:22.794021+00', 0, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (170, 3, 2026, 8, 'acueducto', 9016.64, 4735.52, 1, 0.008000000000000007, false, '2026-10-16 15:31:22.794021+00', 0.008000000000000007, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (171, 3, 2026, 9, 'acueducto', 9016.64, 4735.52, 1, 0.014999999999999902, false, '2026-10-16 15:31:22.794021+00', 0.014999999999999902, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (172, 3, 2026, 10, 'acueducto', 9016.64, 4735.52, 1, 0.02299999999999991, false, '2026-10-16 15:31:22.794021+00', 0.02299999999999991, false);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (173, 3, 2026, 11, 'acueducto', 9296.15584, 4882.32112, 1.031, 0.030999999999999917, true, '2026-10-16 15:31:22.794021+00', 0.030999999999999917, true);
INSERT INTO public.tarifa_vigente (id, empresa_id, anio, mes, servicio, cargo_fijo, cargo_consumo, factor_acumulado, variacion_acum, indexado, calculado_en, var_ipc, indexado_ipc) VALUES (174, 3, 2026, 12, 'acueducto', 9296.15584, 4882.32112, 1.031, 0.005819592628516057, false, '2026-10-16 15:31:22.794021+00', 0.005819592628516057, false);


--
-- Data for Name: usuario_empresa; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Name: auditoria_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auditoria_id_seq', 282, true);


--
-- Name: avance_inversion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.avance_inversion_id_seq', 13, true);


--
-- Name: base_calculo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.base_calculo_id_seq', 85, true);


--
-- Name: carga_mensual_detalle_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.carga_mensual_detalle_id_seq', 152, true);


--
-- Name: carga_mensual_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.carga_mensual_id_seq', 74, true);


--
-- Name: costo_referencia_mensual_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.costo_referencia_mensual_id_seq', 63, true);


--
-- Name: empresa_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.empresa_id_seq', 3, true);


--
-- Name: factor_subsidio_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.factor_subsidio_id_seq', 62, true);


--
-- Name: factura_clase_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.factura_clase_id_seq', 188, true);


--
-- Name: indicador_mensual_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.indicador_mensual_id_seq', 1, false);


--
-- Name: macromedicion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.macromedicion_id_seq', 6, true);


--
-- Name: numerador_mensual_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.numerador_mensual_id_seq', 48, true);


--
-- Name: proyecto_inversion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.proyecto_inversion_id_seq', 7, true);


--
-- Name: resultado_componente_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.resultado_componente_id_seq', 128, true);


--
-- Name: tarifa_vigente_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tarifa_vigente_id_seq', 234, true);


--
-- Name: usuario_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usuario_id_seq', 6, true);


--
-- PostgreSQL database dump complete
--


