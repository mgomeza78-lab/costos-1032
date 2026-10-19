# -*- coding: utf-8 -*-
"""Acceso a datos y, sobre todo, el puente entre la sesión del usuario y la RLS.

La clave del aislamiento está en `scope_conn`: por cada petición abre una
transacción y fija el contexto (app.allow_all / app.empresa_ids / app.user_id)
con `set_config(..., is_local => true)`. A partir de ahí, TODA consulta que la
aplicación ejecute queda filtrada por las políticas RLS de PostgreSQL, sin que
el código tenga que acordarse de poner `WHERE empresa_id = ...`.
"""
from contextlib import contextmanager
from sqlalchemy import create_engine, text
import config

# pool_pre_ping evita conexiones muertas; future=True para estilo 2.0.
engine_app = create_engine(config.DB_APP, pool_pre_ping=True, future=True)
engine_owner = create_engine(config.DB_OWNER, pool_pre_ping=True, future=True)


@contextmanager
def scope_conn(scope):
    """Conexión de aplicación con el contexto de RLS fijado para esta petición.

    `scope` = dict(allow_all: bool, empresa_ids: list[int], user_id: int).
    Un usuario anónimo (scope None) obtiene allow_all=off y sin empresas => no ve filas.
    """
    allow_all = bool(scope and scope.get("allow_all"))
    ids = (scope or {}).get("empresa_ids") or []
    uid = (scope or {}).get("user_id") or 0
    conn = engine_app.connect()
    trans = conn.begin()
    try:
        conn.execute(
            text("SELECT set_config('app.allow_all', :a, true),"
                 "       set_config('app.empresa_ids', :e, true),"
                 "       set_config('app.user_id', :u, true)"),
            {"a": "on" if allow_all else "off",
             "e": ",".join(str(i) for i in ids),
             "u": str(uid)},
        )
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


def authenticate(email):
    """Busca al usuario por correo vía función SECURITY DEFINER (no depende de RLS)."""
    with engine_app.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM app_authenticate(:e)"), {"e": email}
        ).mappings().first()
        return dict(row) if row else None


def resolve_scope(user_id):
    """Alcance (allow_all, empresa_ids) del usuario, vía función SECURITY DEFINER."""
    with engine_app.connect() as conn:
        row = conn.execute(
            text("SELECT allow_all, empresa_ids FROM app_scope(:u)"), {"u": user_id}
        ).mappings().first()
    return {
        "user_id": user_id,
        "allow_all": bool(row["allow_all"]),
        "empresa_ids": list(row["empresa_ids"] or []),
    }


def registrar_intento(email, exito):
    """Registra un intento de login y devuelve el estado de bloqueo."""
    import config
    with engine_app.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM app_registrar_intento(:e,:ok,:mx,:lk)"),
            {"e": email, "ok": exito, "mx": config.MAX_LOGIN_ATTEMPTS, "lk": config.LOCK_MINUTES},
        ).mappings().first()
    return dict(row) if row else {"bloqueado": False, "bloqueado_hasta": None, "intentos": 0}


def set_password(scope, nuevo_hash):
    """Cambia la contraseña del usuario autenticado (via app.user_id)."""
    with scope_conn(scope) as conn:
        conn.execute(text("SELECT app_set_password(:h)"), {"h": nuevo_hash})


def set_mfa(scope, secret, activo):
    """Activa/actualiza o desactiva el MFA del usuario autenticado."""
    with scope_conn(scope) as conn:
        conn.execute(text("SELECT app_set_mfa(:s,:a)"), {"s": secret, "a": activo})


def audit(scope, accion, objeto=None, empresa_id=None, detalle=None):
    """Anota una acción en la bitácora (append-only)."""
    try:
        with scope_conn(scope) as conn:
            conn.execute(
                text("INSERT INTO auditoria(usuario_id,email,accion,objeto,empresa_id,detalle) "
                     "VALUES (:u,:em,:a,:o,:e,:d)"),
                {"u": (scope or {}).get("user_id"), "em": (scope or {}).get("email"),
                 "a": accion, "o": objeto, "e": empresa_id, "d": detalle},
            )
    except Exception:
        pass  # la bitácora nunca debe tumbar la operación principal
