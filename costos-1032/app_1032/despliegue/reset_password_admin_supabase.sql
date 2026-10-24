-- Restablece la contraseña del administrador en Supabase (SQL Editor, como 'postgres').
-- Clave temporal nueva: Ceibas2026*   (deberás cambiarla al entrar)
UPDATE usuario
   SET password_hash     = '$2b$12$Tdm/lhBFvf791nQDsLzA1eXua1mhjpClIrx4dyW0G.H26Mf8VHEH6',
       debe_cambiar_pass = true,
       intentos_fallidos = 0,
       bloqueado_hasta   = NULL,
       activo            = true
 WHERE email = 'mgomeza78@gmail.com';

-- Verifica que actualizó 1 fila:
SELECT email, debe_cambiar_pass, intentos_fallidos, bloqueado_hasta
  FROM usuario WHERE email = 'mgomeza78@gmail.com';
