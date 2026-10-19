# -*- coding: utf-8 -*-
"""Configuración por variables de entorno (con valores por defecto para desarrollo).

Endurecimiento: en producción (APP_ENV=prod) la clave de sesión es obligatoria y la
conexión de la aplicación debe traer contraseña; en desarrollo hay valores por defecto.
"""
import os
import secrets
import sys

APP_ENV = os.environ.get("APP_ENV", "dev").lower()      # 'dev' | 'prod'
IS_PROD = APP_ENV == "prod"

_HOST = os.environ.get("DB_HOST", "localhost")
_PORT = os.environ.get("DB_PORT", "5433")
_APP_PW = os.environ.get("DB_APP_PASSWORD", "")          # contraseña del rol app_user
_OWNER_PW = os.environ.get("DB_OWNER_PASSWORD", "")
# sslmode: vacío en local; 'require' para proveedores gestionados (Supabase, RDS…).
_SSL = os.environ.get("DB_SSLMODE", "")

def _url(user, pw, dbname):
    cred = f"{user}:{pw}" if pw else user
    sufijo = f"?sslmode={_SSL}" if _SSL else ""
    return f"postgresql+psycopg://{cred}@{_HOST}:{_PORT}/{dbname}{sufijo}"

# Nombre de la base (en Supabase/gestionados suele ser 'postgres').
DB_NAME = os.environ.get("DB_NAME", "estudios_1032")
# Conexión de la APLICACIÓN: rol app_user (NO superusuario, NO bypass RLS).
DB_APP = os.environ.get("DB_APP_URL", _url("app_user", _APP_PW, DB_NAME))
# Conexión de ADMINISTRACIÓN de esquema (migraciones y semilla): rol dueño.
DB_OWNER = os.environ.get("DB_OWNER_URL", _url("postgres", _OWNER_PW, DB_NAME))
# Conexión al servidor (sin base) para crear la base de datos si no existe.
DB_SERVER = os.environ.get("DB_SERVER_URL", _url("postgres", _OWNER_PW, "postgres"))

# ---------- Sesión / cookies ----------
_DEV_SECRET = "dev-insecure-change-me-en-produccion"
SECRET_KEY = os.environ.get("APP_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PROD:
        sys.exit("APP_SECRET_KEY es obligatoria en producción (APP_ENV=prod).")
    SECRET_KEY = _DEV_SECRET                              # solo desarrollo
    print("ADVERTENCIA: usando APP_SECRET_KEY de desarrollo; defínala en producción.",
          file=sys.stderr)

COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1" if IS_PROD else "0") == "1"
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "3600"))   # seg. (expiración de sesión)

# ---------- Política de acceso ----------
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCK_MINUTES = int(os.environ.get("LOCK_MINUTES", "15"))
PASSWORD_MIN_LEN = int(os.environ.get("PASSWORD_MIN_LEN", "10"))

# Contraseña de los usuarios semilla (solo para la demostración local).
SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "Cambiar2026*")

# Nombre mostrado en el emisor del TOTP (MFA).
MFA_ISSUER = os.environ.get("MFA_ISSUER", "SICTAA Costos 1032")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
