-- =====================================================================
--  Datos: ICTC (Anexo 5, 2 ejes, Menores de 10 años, DANE sep-2026) +
--  Salario mínimo mensual (SMMLV) 2014-2026. Correr en Supabase.
--  Requiere antes: indices_ipc_smmlv_ictc.sql (columna ictc + tabla salario_minimo).
--  ICTC se adosa a los meses que YA tienen IPC (misma grilla año/mes).
-- =====================================================================

-- ---- ICTC mensual (número índice) — 2 ejes, menores de 10 años ----
UPDATE indice_ipc SET ictc=101.47 WHERE anio=2016 AND mes=1;
UPDATE indice_ipc SET ictc=101.81 WHERE anio=2016 AND mes=2;
UPDATE indice_ipc SET ictc=101.86 WHERE anio=2016 AND mes=3;
UPDATE indice_ipc SET ictc=102.05 WHERE anio=2016 AND mes=4;
UPDATE indice_ipc SET ictc=102.44 WHERE anio=2016 AND mes=5;
UPDATE indice_ipc SET ictc=101.92 WHERE anio=2016 AND mes=6;
UPDATE indice_ipc SET ictc=102.48 WHERE anio=2016 AND mes=7;
UPDATE indice_ipc SET ictc=102.3 WHERE anio=2016 AND mes=8;
UPDATE indice_ipc SET ictc=102.81 WHERE anio=2016 AND mes=9;
UPDATE indice_ipc SET ictc=102.73 WHERE anio=2016 AND mes=10;
UPDATE indice_ipc SET ictc=103.23 WHERE anio=2016 AND mes=11;
UPDATE indice_ipc SET ictc=103.31 WHERE anio=2016 AND mes=12;
UPDATE indice_ipc SET ictc=105.92 WHERE anio=2017 AND mes=1;
UPDATE indice_ipc SET ictc=106.33 WHERE anio=2017 AND mes=2;
UPDATE indice_ipc SET ictc=106.58 WHERE anio=2017 AND mes=3;
UPDATE indice_ipc SET ictc=106.57 WHERE anio=2017 AND mes=4;
UPDATE indice_ipc SET ictc=106.44 WHERE anio=2017 AND mes=5;
UPDATE indice_ipc SET ictc=106.17 WHERE anio=2017 AND mes=6;
UPDATE indice_ipc SET ictc=105.86 WHERE anio=2017 AND mes=7;
UPDATE indice_ipc SET ictc=106.21 WHERE anio=2017 AND mes=8;
UPDATE indice_ipc SET ictc=106.86 WHERE anio=2017 AND mes=9;
UPDATE indice_ipc SET ictc=106.84 WHERE anio=2017 AND mes=10;
UPDATE indice_ipc SET ictc=106.86 WHERE anio=2017 AND mes=11;
UPDATE indice_ipc SET ictc=107.63 WHERE anio=2017 AND mes=12;
UPDATE indice_ipc SET ictc=108.56 WHERE anio=2018 AND mes=1;
UPDATE indice_ipc SET ictc=109.26 WHERE anio=2018 AND mes=2;
UPDATE indice_ipc SET ictc=109.3 WHERE anio=2018 AND mes=3;
UPDATE indice_ipc SET ictc=109.3 WHERE anio=2018 AND mes=4;
UPDATE indice_ipc SET ictc=109.81 WHERE anio=2018 AND mes=5;
UPDATE indice_ipc SET ictc=110.53 WHERE anio=2018 AND mes=6;
UPDATE indice_ipc SET ictc=110.55 WHERE anio=2018 AND mes=7;
UPDATE indice_ipc SET ictc=110.53 WHERE anio=2018 AND mes=8;
UPDATE indice_ipc SET ictc=111.03 WHERE anio=2018 AND mes=9;
UPDATE indice_ipc SET ictc=111.55 WHERE anio=2018 AND mes=10;
UPDATE indice_ipc SET ictc=112.04 WHERE anio=2018 AND mes=11;
UPDATE indice_ipc SET ictc=112.22 WHERE anio=2018 AND mes=12;
UPDATE indice_ipc SET ictc=112.96 WHERE anio=2019 AND mes=1;
UPDATE indice_ipc SET ictc=113.63 WHERE anio=2019 AND mes=2;
UPDATE indice_ipc SET ictc=113.98 WHERE anio=2019 AND mes=3;
UPDATE indice_ipc SET ictc=114.15 WHERE anio=2019 AND mes=4;
UPDATE indice_ipc SET ictc=114.28 WHERE anio=2019 AND mes=5;
UPDATE indice_ipc SET ictc=114.43 WHERE anio=2019 AND mes=6;
UPDATE indice_ipc SET ictc=115.12 WHERE anio=2019 AND mes=7;
UPDATE indice_ipc SET ictc=115.3 WHERE anio=2019 AND mes=8;
UPDATE indice_ipc SET ictc=116.02 WHERE anio=2019 AND mes=9;
UPDATE indice_ipc SET ictc=116.18 WHERE anio=2019 AND mes=10;
UPDATE indice_ipc SET ictc=116.16 WHERE anio=2019 AND mes=11;
UPDATE indice_ipc SET ictc=116.22 WHERE anio=2019 AND mes=12;
UPDATE indice_ipc SET ictc=118.16 WHERE anio=2020 AND mes=1;
UPDATE indice_ipc SET ictc=118.51 WHERE anio=2020 AND mes=2;
UPDATE indice_ipc SET ictc=116.06 WHERE anio=2020 AND mes=3;
UPDATE indice_ipc SET ictc=109.58 WHERE anio=2020 AND mes=4;
UPDATE indice_ipc SET ictc=108.8 WHERE anio=2020 AND mes=5;
UPDATE indice_ipc SET ictc=114.29 WHERE anio=2020 AND mes=6;
UPDATE indice_ipc SET ictc=114.6 WHERE anio=2020 AND mes=7;
UPDATE indice_ipc SET ictc=114.14 WHERE anio=2020 AND mes=8;
UPDATE indice_ipc SET ictc=113.97 WHERE anio=2020 AND mes=9;
UPDATE indice_ipc SET ictc=113.9 WHERE anio=2020 AND mes=10;
UPDATE indice_ipc SET ictc=113.8 WHERE anio=2020 AND mes=11;
UPDATE indice_ipc SET ictc=113.76 WHERE anio=2020 AND mes=12;
UPDATE indice_ipc SET ictc=114.9 WHERE anio=2021 AND mes=1;
UPDATE indice_ipc SET ictc=115.95 WHERE anio=2021 AND mes=2;
UPDATE indice_ipc SET ictc=116.68 WHERE anio=2021 AND mes=3;
UPDATE indice_ipc SET ictc=117.19 WHERE anio=2021 AND mes=4;
UPDATE indice_ipc SET ictc=117.4 WHERE anio=2021 AND mes=5;
UPDATE indice_ipc SET ictc=117.63 WHERE anio=2021 AND mes=6;
UPDATE indice_ipc SET ictc=117.87 WHERE anio=2021 AND mes=7;
UPDATE indice_ipc SET ictc=118.39 WHERE anio=2021 AND mes=8;
UPDATE indice_ipc SET ictc=119.4 WHERE anio=2021 AND mes=9;
UPDATE indice_ipc SET ictc=119.86 WHERE anio=2021 AND mes=10;
UPDATE indice_ipc SET ictc=120.19 WHERE anio=2021 AND mes=11;
UPDATE indice_ipc SET ictc=121.45 WHERE anio=2021 AND mes=12;
UPDATE indice_ipc SET ictc=124.52 WHERE anio=2022 AND mes=1;
UPDATE indice_ipc SET ictc=125.36 WHERE anio=2022 AND mes=2;
UPDATE indice_ipc SET ictc=126.07 WHERE anio=2022 AND mes=3;
UPDATE indice_ipc SET ictc=126.63 WHERE anio=2022 AND mes=4;
UPDATE indice_ipc SET ictc=127.39 WHERE anio=2022 AND mes=5;
UPDATE indice_ipc SET ictc=128.43 WHERE anio=2022 AND mes=6;
UPDATE indice_ipc SET ictc=130.37 WHERE anio=2022 AND mes=7;
UPDATE indice_ipc SET ictc=132.54 WHERE anio=2022 AND mes=8;
UPDATE indice_ipc SET ictc=133.57 WHERE anio=2022 AND mes=9;
UPDATE indice_ipc SET ictc=134.45 WHERE anio=2022 AND mes=10;
UPDATE indice_ipc SET ictc=135.88 WHERE anio=2022 AND mes=11;
UPDATE indice_ipc SET ictc=136.95 WHERE anio=2022 AND mes=12;
UPDATE indice_ipc SET ictc=141.26 WHERE anio=2023 AND mes=1;
UPDATE indice_ipc SET ictc=142.95 WHERE anio=2023 AND mes=2;
UPDATE indice_ipc SET ictc=142.85 WHERE anio=2023 AND mes=3;
UPDATE indice_ipc SET ictc=142.62 WHERE anio=2023 AND mes=4;
UPDATE indice_ipc SET ictc=142.71 WHERE anio=2023 AND mes=5;
UPDATE indice_ipc SET ictc=143.24 WHERE anio=2023 AND mes=6;
UPDATE indice_ipc SET ictc=143.4 WHERE anio=2023 AND mes=7;
UPDATE indice_ipc SET ictc=143.53 WHERE anio=2023 AND mes=8;
UPDATE indice_ipc SET ictc=143.38 WHERE anio=2023 AND mes=9;
UPDATE indice_ipc SET ictc=142.91 WHERE anio=2023 AND mes=10;
UPDATE indice_ipc SET ictc=142.95 WHERE anio=2023 AND mes=11;
UPDATE indice_ipc SET ictc=142.75 WHERE anio=2023 AND mes=12;
UPDATE indice_ipc SET ictc=145.29 WHERE anio=2024 AND mes=1;
UPDATE indice_ipc SET ictc=147.0 WHERE anio=2024 AND mes=2;
UPDATE indice_ipc SET ictc=146.8 WHERE anio=2024 AND mes=3;
UPDATE indice_ipc SET ictc=146.92 WHERE anio=2024 AND mes=4;
UPDATE indice_ipc SET ictc=146.61 WHERE anio=2024 AND mes=5;
UPDATE indice_ipc SET ictc=146.85 WHERE anio=2024 AND mes=6;
UPDATE indice_ipc SET ictc=146.75 WHERE anio=2024 AND mes=7;
UPDATE indice_ipc SET ictc=147.49 WHERE anio=2024 AND mes=8;
UPDATE indice_ipc SET ictc=150.09 WHERE anio=2024 AND mes=9;
UPDATE indice_ipc SET ictc=149.71 WHERE anio=2024 AND mes=10;
UPDATE indice_ipc SET ictc=149.71 WHERE anio=2024 AND mes=11;
UPDATE indice_ipc SET ictc=151.86 WHERE anio=2024 AND mes=12;
UPDATE indice_ipc SET ictc=155.66 WHERE anio=2025 AND mes=1;
UPDATE indice_ipc SET ictc=156.28 WHERE anio=2025 AND mes=2;
UPDATE indice_ipc SET ictc=156.84 WHERE anio=2025 AND mes=3;
UPDATE indice_ipc SET ictc=157.33 WHERE anio=2025 AND mes=4;
UPDATE indice_ipc SET ictc=157.55 WHERE anio=2025 AND mes=5;
UPDATE indice_ipc SET ictc=157.81 WHERE anio=2025 AND mes=6;
UPDATE indice_ipc SET ictc=157.64 WHERE anio=2025 AND mes=7;
UPDATE indice_ipc SET ictc=157.74 WHERE anio=2025 AND mes=8;
UPDATE indice_ipc SET ictc=157.42 WHERE anio=2025 AND mes=9;
UPDATE indice_ipc SET ictc=157.85 WHERE anio=2025 AND mes=10;
UPDATE indice_ipc SET ictc=157.92 WHERE anio=2025 AND mes=11;
UPDATE indice_ipc SET ictc=158.1 WHERE anio=2025 AND mes=12;
UPDATE indice_ipc SET ictc=164.14 WHERE anio=2026 AND mes=1;
UPDATE indice_ipc SET ictc=165.72 WHERE anio=2026 AND mes=2;
UPDATE indice_ipc SET ictc=166.45 WHERE anio=2026 AND mes=3;
UPDATE indice_ipc SET ictc=167.32 WHERE anio=2026 AND mes=4;
UPDATE indice_ipc SET ictc=168.61 WHERE anio=2026 AND mes=5;
UPDATE indice_ipc SET ictc=168.31 WHERE anio=2026 AND mes=6;
UPDATE indice_ipc SET ictc=168.26 WHERE anio=2026 AND mes=7;
UPDATE indice_ipc SET ictc=168.28 WHERE anio=2026 AND mes=8;
UPDATE indice_ipc SET ictc=168.33 WHERE anio=2026 AND mes=9;

-- ---- Salario mínimo mensual legal vigente (SMMLV), valor mensual ----
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2014,616000,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2015,644350,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2016,689455,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2017,737717,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2018,781242,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2019,828116,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2020,877803,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2021,908526,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2022,1000000,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2023,1160000,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2024,1300000,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2025,1423500,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;
INSERT INTO salario_minimo(anio,valor,fuente,procedencia) VALUES (2026,1750905,'Decreto SMMLV','normativa') ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, procedencia=excluded.procedencia;

-- ---- Verificación ----
SELECT (SELECT count(*) FROM indice_ipc WHERE ictc IS NOT NULL) AS meses_ictc,
       (SELECT count(*) FROM salario_minimo) AS anios_smmlv,
       (SELECT ictc FROM indice_ipc WHERE anio=2025 AND mes=12) AS ictc_dic2025,
       (SELECT valor FROM salario_minimo WHERE anio=2026) AS smmlv_2026;
