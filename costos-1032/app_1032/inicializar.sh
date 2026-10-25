#!/bin/bash
# Inicializa la base: crea la BD si no existe, corre migraciones (esquema + RLS) y la semilla.
# Requiere PostgreSQL en marcha y las variables DB_HOST/DB_PORT (por defecto localhost:5433).
set -e
HOST="${DB_HOST:-localhost}"; PORT="${DB_PORT:-5433}"; OWNER="${DB_OWNER_ROLE:-postgres}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "1/3  Base de datos estudios_1032…"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -tc "SELECT 1 FROM pg_database WHERE datname='estudios_1032'" \
  | grep -q 1 || createdb -h "$HOST" -p "$PORT" -U "$OWNER" estudios_1032

echo "2/3  Migraciones (esquema + Row-Level Security)…"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/001_schema.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/002_rls.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/003_hardening.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/004_operacion.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/005_cargue.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/006_recalculo.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/007_inversiones.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/008_periodos.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/009_subsidios.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/010_territorio.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/011_divipola_data.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/012_aps.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/013_cargue_bcr.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/014_bcr0_inicio.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/015_poir_cmi.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/016_costos_particulares_coc.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/017_ccp_fap.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/018_bcr_serie_segmento.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/019_indices_macro.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/020_catalogo_empresa.sql"
psql -h "$HOST" -p "$PORT" -U "$OWNER" -d estudios_1032 -v ON_ERROR_STOP=1 -q -f "$DIR/sql/021_resultados_aprobaciones.sql"

echo "3/3  Semilla (catálogo + 3 empresas + usuarios + operación + recálculo + inversiones)…"
python3 "$DIR/seed.py"
python3 "$DIR/seed_operacion.py"
python3 "$DIR/seed_recalculo.py"
python3 "$DIR/seed_inversiones.py"
echo "Listo."
