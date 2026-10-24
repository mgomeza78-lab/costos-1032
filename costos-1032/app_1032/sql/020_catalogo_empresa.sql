-- =====================================================================
--  020_catalogo_empresa.sql — catálogo de clasificación de cuentas
--  (cuenta PUC → subcomponente/componente de la Res. CRA 1032) que cada
--  empresa puede subir. Si una empresa no tiene el suyo, el backend usa el
--  catálogo por defecto (el de Las Ceibas). Se ejecuta como el rol dueño.
-- =====================================================================

CREATE TABLE IF NOT EXISTS catalogo_empresa (
  empresa_id      integer PRIMARY KEY REFERENCES empresa(id) ON DELETE CASCADE,
  csv_texto       text NOT NULL,            -- catálogo CSV crudo (codigo_norm, subcomponente, componente, traslado…)
  n_cuentas       integer,                  -- cuentas con componente reconocidas al cargar
  nombre_archivo  text,
  cargado_por     integer REFERENCES usuario(id),
  cargado_en      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE catalogo_empresa ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cate_all ON catalogo_empresa;
CREATE POLICY cate_all ON catalogo_empresa FOR ALL
  USING (app_allow_all() OR empresa_id = ANY (app_empresa_ids()))
  WITH CHECK (app_allow_all() OR empresa_id = ANY (app_empresa_ids()));

GRANT SELECT, INSERT, UPDATE, DELETE ON catalogo_empresa TO app_user;
