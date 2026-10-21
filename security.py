# -*- coding: utf-8 -*-
"""Seguridad de aplicación: contraseñas (bcrypt), sesión, CSRF, política y MFA (TOTP)."""
import re
import secrets
import bcrypt
import pyotp
import segno
import io
import config


# ---------------------------------------------------------------- contraseñas
def hash_password(plain: str) -> str:
    # bcrypt opera sobre los primeros 72 bytes; recortamos explícitamente.
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def password_issues(pw: str):
    """Lista de incumplimientos de la política de contraseñas (vacía = cumple)."""
    problemas = []
    if len(pw) < config.PASSWORD_MIN_LEN:
        problemas.append(f"mínimo {config.PASSWORD_MIN_LEN} caracteres")
    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]", pw):
        problemas.append("al menos una letra")
    if not re.search(r"\d", pw):
        problemas.append("al menos un número")
    if not re.search(r"[^A-Za-z0-9]", pw):
        problemas.append("al menos un símbolo")
    return problemas


# ---------------------------------------------------------------- sesión
def session_user(request):
    u = request.session.get("user")
    return u if u else None


def scope_of(user):
    if not user:
        return {"allow_all": False, "empresa_ids": [], "user_id": 0}
    return {
        "allow_all": user.get("allow_all", False),
        "empresa_ids": user.get("empresa_ids", []),
        "user_id": user.get("user_id", 0),
        "email": user.get("email"),
    }


# ---------------------------------------------------------------- CSRF
def ensure_csrf(request) -> str:
    """Devuelve el token CSRF de la sesión, creándolo si no existe."""
    tok = request.session.get("csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session["csrf"] = tok
    return tok


def csrf_ok(request, enviado: str) -> bool:
    guardado = request.session.get("csrf") or ""
    return bool(enviado) and secrets.compare_digest(str(enviado), guardado)


# ---------------------------------------------------------------- MFA (TOTP)
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=config.MFA_ISSUER)


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(str(code).strip().replace(" ", ""), valid_window=1)
    except Exception:
        return False


def qr_data_uri(uri: str) -> str:
    """QR del otpauth:// como data URI SVG (sin dependencias de imagen binaria)."""
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=4, border=2)
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
