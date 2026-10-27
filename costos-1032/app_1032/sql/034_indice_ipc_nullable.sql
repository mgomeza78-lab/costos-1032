-- =====================================================================
--  034_indice_ipc_nullable.sql — el IPC total deja de ser obligatorio por mes.
--   Cada índice (IPC, IPCs, ICTC) se publica con rezagos distintos, así que un
--   mes puede tener uno sin los otros (p. ej. ICTC de sep-2026 cuando el IPC
--   solo está hasta ago-2026). Las vistas ya ignoran los nulos por columna.
--  Idempotente.
-- =====================================================================

ALTER TABLE indice_ipc ALTER COLUMN indice DROP NOT NULL;
