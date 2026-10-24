# -*- coding: utf-8 -*-
"""Aplicación web — Fundación multiempresa + acceso (Res. CRA 1032/2026).

Capa de acceso y aislamiento sobre el núcleo de cálculo ya validado:
  · autenticación y 4 roles (Administrador / Analista / Empresa / Auditor);
  · aislamiento por empresa con Row-Level Security de PostgreSQL;
  · el núcleo validado conectado a la base (recálculo por empresa).

Endurecimiento: cabeceras de seguridad, cookie de sesión endurecida con expiración,
CSRF en todos los formularios, bloqueo por intentos fallidos, MFA (TOTP) opcional,
política de contraseñas y auto-servicio de contraseña/MFA.
"""
import os
import re
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

import config, db, rbac, nucleo_service
import operacion_service as ops
import indices_service as ix
import ccp_view as cv
import recalculo_service as rc
import inversiones_service as inv
import subsidios_service as subs
import dashboard_service as dash
import territorio_service as terr
import aps_service as aps
import costos_service as cpart
import bcr_service as bcr
import poir_cmi_service as poir
import ccp_service as ccp
import periodos as per
import ingesta
import lector_balance as lb
import clasificador as clf
import security as sec
from security import (verify_password, session_user, scope_of, ensure_csrf, csrf_ok,
                      hash_password, password_issues)

app = FastAPI(title="Estudios de costos CRA 1032 — plataforma multiempresa")


# ---------------- cabeceras de seguridad ----------------
class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; object-src 'none'")
        if config.IS_PROD:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp


app.add_middleware(SecurityHeaders)
app.add_middleware(
    SessionMiddleware, secret_key=config.SECRET_KEY, session_cookie="sesion",
    max_age=config.SESSION_MAX_AGE, same_site="strict", https_only=config.COOKIE_SECURE)
app.mount("/static", StaticFiles(directory=os.path.join(config.BASE_DIR, "static")), name="static")
tpl = Jinja2Templates(directory=os.path.join(config.BASE_DIR, "templates"))
tpl.env.globals["rbac"] = rbac


def _fmt_valor(valor, unidad=""):
    """Formato numérico colombiano: miles con '.', decimales con ','."""
    if valor is None:
        return "—"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    dec = 2 if (unidad and ("m³" in unidad or "susc" in unidad)) else 0
    s = f"{v:,.{dec}f}"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")


tpl.env.filters["valor"] = _fmt_valor
tpl.env.filters["anio_tar"] = per.corto          # etiqueta corta del año tarifario (Inicio, Año 3…)
tpl.env.filters["anio_tar_full"] = per.etiqueta  # etiqueta completa
tpl.env.filters["anio_tar_base"] = per.etiqueta_base  # período al que pertenece un AÑO de línea base
tpl.env.globals["PERIODOS"] = per.PERIODOS


# ------------------------------------------------------------------ helpers
def _ctx(request, **extra):
    user = session_user(request)
    base = {"request": request, "user": user,
            "csrf_token": ensure_csrf(request),
            "msg": request.query_params.get("msg"),
            "err": request.query_params.get("err")}
    base.update(extra)
    return base


def _need_login(request):
    return None if session_user(request) else RedirectResponse("/login", status_code=303)


def _bad_csrf(request, csrf):
    """Devuelve una redirección si el token CSRF es inválido, o None si es válido."""
    if not csrf_ok(request, csrf):
        destino = request.url.path
        return RedirectResponse(f"{destino}?err=Token+de+seguridad+inválido,+reintente", status_code=303)
    return None


def _next_or(nxt, default):
    """Destino de redirección: respeta un `next` interno seguro, o usa el predeterminado."""
    nxt = (nxt or "").strip()
    if nxt.startswith("/empresa/") and "//" not in nxt and " " not in nxt and "\n" not in nxt:
        return nxt
    return default


def _dest(nxt, default, query):
    base = _next_or(nxt, default)
    return f"{base}{'&' if '?' in base else '?'}{query}"


def _destino_inicio(user):
    """Pantalla de entrada tras el login. El administrador y el analista ven el
    panel de empresas; los demás usuarios (empresa/auditor) van directo a la
    empresa que tengan asignada."""
    if not user:
        return "/login"
    if rbac.can(user, "ver_otras_empresas"):      # admin + analista → panel
        return "/panel"
    eid = user.get("empresa_id")
    if not eid:
        ids = user.get("empresa_ids") or []
        eid = ids[0] if ids else None
    return f"/empresa/{eid}" if eid else "/panel"


def _leer_csv(archivo):
    """Lee el CSV subido con detección de codificación (los reportes del SUI son Latin-1)."""
    raw = archivo.file.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace")


def _complete_login(request, u):
    scope = db.resolve_scope(u["id"])
    request.session.clear()                       # regeneración de sesión (anti-fijación)
    request.session["user"] = {
        "user_id": u["id"], "email": u["email"], "nombre": u["nombre"],
        "rol": u["rol_codigo"], "empresa_id": u["empresa_id"],
        "allow_all": scope["allow_all"], "empresa_ids": scope["empresa_ids"],
        "debe_cambiar": bool(u["debe_cambiar_pass"]),
    }
    db.audit(scope_of(request.session["user"]), "login", "sesión")


# ------------------------------------------------------------------ auth
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    u = session_user(request)
    return RedirectResponse(_destino_inicio(u) if u else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if (u := session_user(request)):
        return RedirectResponse(_destino_inicio(u), status_code=303)
    return tpl.TemplateResponse(request, "login.html", _ctx(request))


@app.post("/login")
def login_post(request: Request, email: str = Form(...), password: str = Form(...),
               csrf: str = Form("")):
    if (bad := _bad_csrf(request, csrf)):
        return bad
    email = email.strip()
    u = db.authenticate(email)
    now = datetime.now(timezone.utc)
    if u and u["bloqueado_hasta"] and u["bloqueado_hasta"] > now:
        db.audit({"email": email}, "login_bloqueado", "sesión")
        return RedirectResponse("/login?err=Cuenta+bloqueada+temporalmente+por+intentos+fallidos",
                                status_code=303)
    ok = bool(u) and u["activo"] and verify_password(password, u["password_hash"])
    if not ok:
        st = db.registrar_intento(email, False)
        db.audit({"email": email}, "login_fallido", "sesión",
                 detalle=f"intentos={st.get('intentos')}")
        if st.get("bloqueado"):
            return RedirectResponse(
                f"/login?err=Cuenta+bloqueada+{config.LOCK_MINUTES}+min+por+intentos+fallidos",
                status_code=303)
        return RedirectResponse("/login?err=Credenciales+inválidas", status_code=303)
    db.registrar_intento(email, True)                 # reinicia el contador
    if u["mfa_activo"] and u["mfa_secret"]:           # segundo factor pendiente
        request.session.clear()
        request.session["mfa_pending"] = {"id": u["id"], "email": u["email"]}
        return RedirectResponse("/mfa", status_code=303)
    _complete_login(request, u)
    destino = ("/cuenta?msg=Debe+cambiar+su+contraseña" if u["debe_cambiar_pass"]
               else _destino_inicio(session_user(request)))
    return RedirectResponse(destino, status_code=303)


@app.get("/mfa", response_class=HTMLResponse)
def mfa_form(request: Request):
    if not request.session.get("mfa_pending"):
        return RedirectResponse("/login", status_code=303)
    return tpl.TemplateResponse(request, "mfa.html", _ctx(request))


@app.post("/mfa")
def mfa_post(request: Request, codigo: str = Form(...), csrf: str = Form("")):
    if (bad := _bad_csrf(request, csrf)):
        return bad
    pend = request.session.get("mfa_pending")
    if not pend:
        return RedirectResponse("/login", status_code=303)
    u = db.authenticate(pend["email"])
    if u and sec.verify_totp(u["mfa_secret"], codigo):
        request.session.pop("mfa_pending", None)
        _complete_login(request, u)
        db.audit(scope_of(request.session["user"]), "login_mfa_ok", "sesión")
        return RedirectResponse(_destino_inicio(session_user(request)), status_code=303)
    db.audit({"email": pend["email"]}, "login_mfa_fallido", "sesión")
    return RedirectResponse("/mfa?err=Código+MFA+inválido", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login?msg=Sesión+cerrada", status_code=303)


# ------------------------------------------------------------------ cuenta (auto-servicio)
@app.get("/cuenta", response_class=HTMLResponse)
def cuenta(request: Request):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        info = conn.execute(text(
            "SELECT email, nombre, mfa_activo, debe_cambiar_pass, ultimo_login "
            "FROM usuario WHERE id=:u"), {"u": user["user_id"]}).mappings().first()
    mfa_setup = request.session.get("mfa_setup")
    qr = uri = None
    if mfa_setup:
        uri = sec.totp_uri(mfa_setup, user["email"])
        qr = sec.qr_data_uri(uri)
    return tpl.TemplateResponse(request, "cuenta.html", _ctx(
        request, info=info, mfa_setup=bool(mfa_setup), qr=qr, otpuri=uri,
        min_len=config.PASSWORD_MIN_LEN))


@app.post("/cuenta/password")
def cuenta_password(request: Request, actual: str = Form(...), nueva: str = Form(...),
                    confirmar: str = Form(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    u = db.authenticate(user["email"])
    if not u or not verify_password(actual, u["password_hash"]):
        return RedirectResponse("/cuenta?err=La+contraseña+actual+no+coincide", status_code=303)
    if nueva != confirmar:
        return RedirectResponse("/cuenta?err=La+confirmación+no+coincide", status_code=303)
    problemas = password_issues(nueva)
    if problemas:
        return RedirectResponse("/cuenta?err=Contraseña+débil:+" + ", ".join(problemas).replace(" ", "+"),
                                status_code=303)
    db.set_password(scope_of(user), hash_password(nueva))
    user["debe_cambiar"] = False
    request.session["user"] = user
    db.audit(scope_of(user), "cambio_password", "usuario", None, user["email"])
    return RedirectResponse("/cuenta?msg=Contraseña+actualizada", status_code=303)


@app.post("/cuenta/mfa/iniciar")
def mfa_iniciar(request: Request, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    request.session["mfa_setup"] = sec.new_totp_secret()
    return RedirectResponse("/cuenta?msg=Escanee+el+código+y+confirme", status_code=303)


@app.post("/cuenta/mfa/confirmar")
def mfa_confirmar(request: Request, codigo: str = Form(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    secret = request.session.get("mfa_setup")
    if not secret or not sec.verify_totp(secret, codigo):
        return RedirectResponse("/cuenta?err=Código+inválido,+intente+de+nuevo", status_code=303)
    db.set_mfa(scope_of(user), secret, True)
    request.session.pop("mfa_setup", None)
    db.audit(scope_of(user), "mfa_activado", "usuario", None, user["email"])
    return RedirectResponse("/cuenta?msg=MFA+activado", status_code=303)


@app.post("/cuenta/mfa/desactivar")
def mfa_desactivar(request: Request, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    db.set_mfa(scope_of(user), None, False)
    request.session.pop("mfa_setup", None)
    db.audit(scope_of(user), "mfa_desactivado", "usuario", None, user["email"])
    return RedirectResponse("/cuenta?msg=MFA+desactivado", status_code=303)


# ------------------------------------------------------------------ panel / empresas
@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        empresas = conn.execute(text(
            "SELECT e.id, e.codigo, e.nombre, e.municipio, e.segmento_id, "
            "       e.presta_ac, e.presta_al, "
            "       (SELECT count(*) FROM resultado_componente rc WHERE rc.empresa_id=e.id) AS n_res "
            "FROM empresa e ORDER BY e.nombre")).mappings().all()
    return tpl.TemplateResponse(request, "panel.html", _ctx(request, empresas=empresas))


@app.get("/empresa/{eid}", response_class=HTMLResponse)
def empresa_detail(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:                       # RLS lo oculta si no es su empresa
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        res = conn.execute(text(
            "SELECT servicio, componente, valor, unidad, procedencia, fuente, articulo, calculado_en "
            "FROM resultado_componente WHERE empresa_id=:e "
            "ORDER BY servicio, "
            " array_position(ARRAY['CMA','CMO','CMI','CMICT','CARGO_FIJO','CARGO_CONSUMO','BCR0'], componente)"),
            {"e": eid}).mappings().all()
    por_servicio = {}
    for row in res:
        por_servicio.setdefault(row["servicio"], []).append(row)
    return tpl.TemplateResponse(request, "empresa.html", _ctx(
        request, emp=emp, por_servicio=por_servicio,
        tiene_perfil=nucleo_service.perfil_existe(emp["codigo"])))


@app.get("/empresa/{eid}/ccp", response_class=HTMLResponse)
def empresa_ccp(request: Request, eid: int, anio: int = None):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        datos = cv.resumen(conn, eid, anio)
    return tpl.TemplateResponse(request, "ccp.html", _ctx(request, emp=emp, ccp=datos, meses=ops.MESES))


@app.post("/empresa/{eid}/recalcular")
def recalcular(request: Request, eid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "recalcular"):
        return RedirectResponse(f"/empresa/{eid}?err=No+autorizado+para+recalcular", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id, codigo FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        if not nucleo_service.perfil_existe(emp["codigo"]):
            return RedirectResponse(f"/empresa/{eid}?err=Sin+perfil+de+cálculo", status_code=303)
        filas = nucleo_service.calcular(emp["codigo"])
        for f in filas:
            conn.execute(text(
                "INSERT INTO resultado_componente "
                "(empresa_id,servicio,componente,valor,unidad,procedencia,fuente,articulo) "
                "VALUES (:e,:s,:c,:v,:u,:p,:f,:a) "
                "ON CONFLICT (empresa_id,servicio,componente) DO UPDATE SET "
                " valor=excluded.valor, unidad=excluded.unidad, procedencia=excluded.procedencia, "
                " fuente=excluded.fuente, articulo=excluded.articulo, calculado_en=now()"),
                {"e": eid, "s": f["servicio"], "c": f["componente"], "v": f["valor"],
                 "u": f["unidad"], "p": f["procedencia"], "f": f["fuente"], "a": f["articulo"]})
    db.audit(scope_of(user), "recalcular", "empresa", eid, f"{len(filas)} componentes")
    return RedirectResponse(f"/empresa/{eid}?msg=Recálculo+aplicado+({len(filas)}+componentes)", status_code=303)


# ------------------------------------------------------------------ alta de empresa (admin)
@app.get("/empresa-nueva", response_class=HTMLResponse)
def empresa_nueva_form(request: Request):
    if (r := _need_login(request)):
        return r
    if not rbac.can(session_user(request), "crear_empresa"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(session_user(request))) as conn:
        segs = conn.execute(text("SELECT id, nombre, susc_min, susc_max FROM segmento ORDER BY id")).mappings().all()
        deptos = terr.departamentos(conn)
        munis = terr.municipios(conn)
        existentes = {r0[0] for r0 in conn.execute(text("SELECT codigo FROM empresa")).all()}
    perfiles = [c for c in nucleo_service.codigos_disponibles() if c not in existentes]
    return tpl.TemplateResponse(request, "empresa_nueva.html", _ctx(
        request, segmentos=segs, perfiles=perfiles, departamentos=deptos, municipios=munis))


@app.post("/empresa-nueva")
def empresa_nueva_post(request: Request, codigo: str = Form(...), nombre: str = Form(""),
                       suscriptores: str = Form(""), codigo_sui: str = Form(""),
                       fecha_688: str = Form(""), fecha_1032: str = Form(""),
                       aps_items: list[str] = Form([], alias="aps"), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "crear_empresa"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)

    def _i(x):
        d = "".join(ch for ch in (x or "") if ch.isdigit())
        return int(d) if d else None

    codigo = codigo.strip().upper().replace(" ", "_")
    base = nucleo_service.perfil_resumen(codigo) if nucleo_service.perfil_existe(codigo) else {}
    susc = _i(suscriptores)

    # Municipios atendidos con su servicio por APS ("coddane:servicio")
    pares, vistos = [], set()
    for a in (aps_items or []):
        cod, _, serv = (a or "").partition(":")
        cod = cod.strip(); serv = (serv or "ambos").strip().lower()
        if cod.isdigit() and len(cod) == 5 and serv in ("ac", "al", "ambos") and cod not in vistos:
            vistos.add(cod); pares.append((cod, serv))
    presta_ac = any(s in ("ac", "ambos") for _, s in pares)
    presta_al = any(s in ("al", "ambos") for _, s in pares)
    f688 = (base.get("fecha_inicio_688") or fecha_688.strip() or "2016-07-01")
    f1032 = (base.get("fecha_inicio_1032") or fecha_1032.strip() or "2026-07-01")
    tardia = bool(base.get("aplicacion_1032_tardia")) or (str(f1032) > "2026-07-01")
    try:
        with db.scope_conn(scope_of(user)) as conn:
            seg_sug, _m = terr.segmento_por_suscriptores(conn, susc)
            seg = base.get("segmento") or seg_sug or 2      # automático por suscriptores
            segrow = conn.execute(text("SELECT r, kct FROM segmento WHERE id=:s"),
                                  {"s": seg}).mappings().first()
            data = {
                "codigo": codigo, "nombre": nombre.strip() or base.get("nombre") or codigo,
                "municipio": base.get("municipio"), "segmento_id": seg,
                "presta_ac": presta_ac or bool(base.get("presta_ac")),
                "presta_al": presta_al or bool(base.get("presta_al")),
                "esquema": base.get("esquema"),
                "r": base.get("r") or (float(segrow["r"]) if segrow else None),
                "kct": base.get("kct") or (float(segrow["kct"]) if segrow else None),
                "f688": f688 or None, "f1032": f1032 or None, "tardia": tardia,
                "sui": codigo_sui.strip() or None, "naps": len(pares) or None, "sseg": susc,
            }
            eid = conn.execute(text(
                "INSERT INTO empresa (codigo,nombre,nit,municipio,segmento_id,presta_ac,presta_al,"
                " esquema,r,kct,fecha_inicio_688,fecha_inicio_1032,aplicacion_1032_tardia,"
                " codigo_sui,n_aps,suscriptores_seg) "
                "VALUES (:codigo,:nombre,NULL,:municipio,:segmento_id,:presta_ac,:presta_al,"
                " :esquema,:r,:kct,:f688,:f1032,:tardia,:sui,:naps,:sseg) RETURNING id"), data).scalar()
            terr.set_municipios(conn, eid, [c for c, _ in pares])
            for idx, (cod, serv) in enumerate(pares, start=1):
                aps.guardar(conn, eid, cod, {"servicios": serv, "numero_aps": idx}, user["user_id"])
            if pares and not data["municipio"]:
                prim = conn.execute(text(
                    "SELECT m.nombre || ' (' || d.nombre || ')' FROM municipio m "
                    "JOIN departamento d ON d.cod_dane = m.cod_dpto WHERE m.cod_dane = :c"),
                    {"c": pares[0][0]}).scalar()
                if prim:
                    conn.execute(text("UPDATE empresa SET municipio=:m WHERE id=:e"), {"m": prim, "e": eid})
    except Exception as e:
        return RedirectResponse(f"/empresa-nueva?err=No+se+pudo+crear+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "crear_empresa", "empresa", None, codigo)
    return RedirectResponse("/panel?msg=Empresa+creada:+" + codigo, status_code=303)


# ------------------------------------------------------------------ editar empresa (admin + analista)
@app.get("/empresa/{eid}/editar", response_class=HTMLResponse)
def empresa_editar_form(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    if not rbac.can(user, "editar_empresa"):
        return RedirectResponse(f"/empresa/{eid}?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        segs = conn.execute(text("SELECT id, nombre, susc_min, susc_max FROM segmento ORDER BY id")).mappings().all()
        deptos = terr.departamentos(conn)
        munis = terr.municipios(conn)
        # municipios ya atendidos con el servicio declarado en su APS (si existe)
        actuales = conn.execute(text(
            "SELECT em.cod_dane, m.nombre AS municipio, d.nombre AS departamento, "
            "       COALESCE(a.servicios, 'ambos') AS servicios "
            "FROM empresa_municipio em "
            "JOIN municipio m ON m.cod_dane = em.cod_dane "
            "JOIN departamento d ON d.cod_dane = m.cod_dpto "
            "LEFT JOIN aps a ON a.empresa_id = em.empresa_id AND a.cod_dane = em.cod_dane "
            "WHERE em.empresa_id = :e ORDER BY d.nombre, m.nombre"),
            {"e": eid}).mappings().all()
    return tpl.TemplateResponse(request, "empresa_editar.html", _ctx(
        request, emp=emp, segmentos=segs, departamentos=deptos, municipios=munis,
        actuales=actuales))


@app.post("/empresa/{eid}/editar")
def empresa_editar_post(request: Request, eid: int, nombre: str = Form(""),
                        suscriptores: str = Form(""), codigo_sui: str = Form(""),
                        fecha_688: str = Form(""), fecha_1032: str = Form(""),
                        aps_items: list[str] = Form([], alias="aps"), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "editar_empresa"):
        return RedirectResponse(f"/empresa/{eid}?err=No+autorizado", status_code=303)

    def _i(x):
        d = "".join(ch for ch in (x or "") if ch.isdigit())
        return int(d) if d else None

    susc = _i(suscriptores)
    pares, vistos = [], set()
    for a in (aps_items or []):
        cod, _, serv = (a or "").partition(":")
        cod = cod.strip(); serv = (serv or "ambos").strip().lower()
        if cod.isdigit() and len(cod) == 5 and serv in ("ac", "al", "ambos") and cod not in vistos:
            vistos.add(cod); pares.append((cod, serv))
    presta_ac = any(s in ("ac", "ambos") for _, s in pares)
    presta_al = any(s in ("al", "ambos") for _, s in pares)
    f688 = fecha_688.strip() or None
    f1032 = fecha_1032.strip() or None
    tardia = bool(f1032 and str(f1032) > "2026-07-01")
    try:
        with db.scope_conn(scope_of(user)) as conn:
            emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
            if not emp:
                return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
            # Segmento automático por suscriptores; si cambia, se refrescan r y kct.
            seg_sug, _m = terr.segmento_por_suscriptores(conn, susc) if susc else (None, None)
            seg = seg_sug or emp["segmento_id"]
            r_val, kct_val = emp["r"], emp["kct"]
            if seg != emp["segmento_id"]:
                sr = conn.execute(text("SELECT r, kct FROM segmento WHERE id=:s"),
                                  {"s": seg}).mappings().first()
                if sr:
                    r_val, kct_val = float(sr["r"]), float(sr["kct"])
            data = {
                "e": eid, "nombre": nombre.strip() or emp["nombre"], "segmento_id": seg,
                "presta_ac": presta_ac, "presta_al": presta_al, "r": r_val, "kct": kct_val,
                "f688": f688 or emp["fecha_inicio_688"], "f1032": f1032 or emp["fecha_inicio_1032"],
                "tardia": tardia, "sui": codigo_sui.strip() or emp["codigo_sui"],
                "naps": len(pares) or None, "sseg": susc if susc is not None else emp["suscriptores_seg"],
            }
            conn.execute(text(
                "UPDATE empresa SET nombre=:nombre, segmento_id=:segmento_id, presta_ac=:presta_ac, "
                " presta_al=:presta_al, r=:r, kct=:kct, fecha_inicio_688=:f688, fecha_inicio_1032=:f1032, "
                " aplicacion_1032_tardia=:tardia, codigo_sui=:sui, n_aps=:naps, suscriptores_seg=:sseg "
                "WHERE id=:e"), data)
            # Reconciliación de municipios/APS sin destruir la configuración ya hecha:
            actuales = {row[0] for row in conn.execute(text(
                "SELECT cod_dane FROM empresa_municipio WHERE empresa_id=:e"), {"e": eid}).all()}
            objetivo = {c for c, _ in pares}
            for cod in actuales - objetivo:                 # municipios retirados
                conn.execute(text("DELETE FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                             {"e": eid, "c": cod})
                conn.execute(text("DELETE FROM empresa_municipio WHERE empresa_id=:e AND cod_dane=:c"),
                             {"e": eid, "c": cod})
            for idx, (cod, serv) in enumerate(pares, start=1):
                conn.execute(text("INSERT INTO empresa_municipio(empresa_id,cod_dane) VALUES (:e,:c) "
                                  "ON CONFLICT DO NOTHING"), {"e": eid, "c": cod})
                existe = conn.execute(text("SELECT 1 FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                                      {"e": eid, "c": cod}).first()
                if existe:                                   # conserva el detalle del APS; solo refresca el servicio
                    conn.execute(text(
                        "UPDATE aps SET servicios=:s, numero_aps=COALESCE(numero_aps,:n), "
                        " actualizado_por=:u, actualizado_en=now() WHERE empresa_id=:e AND cod_dane=:c"),
                        {"s": serv, "n": idx, "u": user["user_id"], "e": eid, "c": cod})
                else:
                    aps.guardar(conn, eid, cod, {"servicios": serv, "numero_aps": idx}, user["user_id"])
            # Municipio principal (rótulo) = primer APS, si quedó alguno.
            if pares:
                prim = conn.execute(text(
                    "SELECT m.nombre || ' (' || d.nombre || ')' FROM municipio m "
                    "JOIN departamento d ON d.cod_dane = m.cod_dpto WHERE m.cod_dane = :c"),
                    {"c": pares[0][0]}).scalar()
                if prim:
                    conn.execute(text("UPDATE empresa SET municipio=:m WHERE id=:e"), {"m": prim, "e": eid})
    except Exception as e:
        return RedirectResponse(f"/empresa/{eid}/editar?err=No+se+pudo+guardar+({type(e).__name__})",
                                status_code=303)
    db.audit(scope_of(user), "editar_empresa", "empresa", eid, emp["codigo"])
    return RedirectResponse(f"/empresa/{eid}/aps?msg=Empresa+actualizada;+ajuste+el+detalle+de+cada+APS",
                            status_code=303)


# ------------------------------------------------------------------ usuarios (admin)
@app.get("/usuarios", response_class=HTMLResponse)
def usuarios(request: Request):
    if (r := _need_login(request)):
        return r
    if not rbac.can(session_user(request), "administrar_usuarios"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(session_user(request))) as conn:
        us = conn.execute(text(
            "SELECT u.id,u.email,u.nombre,u.activo,u.mfa_activo,r.codigo AS rol,e.nombre AS empresa "
            "FROM usuario u JOIN rol r ON r.id=u.rol_id LEFT JOIN empresa e ON e.id=u.empresa_id "
            "ORDER BY r.id, u.nombre")).mappings().all()
        empresas = conn.execute(text("SELECT id,nombre FROM empresa ORDER BY nombre")).mappings().all()
        roles = conn.execute(text("SELECT codigo,nombre FROM rol ORDER BY id")).mappings().all()
        asig_rows = conn.execute(text(
            "SELECT usuario_id, empresa_id FROM usuario_empresa")).mappings().all()
    asignaciones = {}
    for row in asig_rows:
        asignaciones.setdefault(row["usuario_id"], []).append(row["empresa_id"])
    emp_nombre = {e["id"]: e["nombre"] for e in empresas}
    return tpl.TemplateResponse(request, "usuarios.html",
                                _ctx(request, usuarios=us, empresas=empresas, roles=roles,
                                     asignaciones=asignaciones, emp_nombre=emp_nombre,
                                     min_len=config.PASSWORD_MIN_LEN))


@app.post("/usuarios")
def usuarios_post(request: Request, email: str = Form(...), nombre: str = Form(...),
                  rol: str = Form(...), empresa_id: str = Form(""),
                  empresas_analista: list[str] = Form([]), password: str = Form(...),
                  csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_usuarios"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    problemas = password_issues(password)
    if problemas:
        return RedirectResponse("/usuarios?err=Contraseña+débil:+" + ", ".join(problemas).replace(" ", "+"),
                                status_code=303)
    eid = int(empresa_id) if (empresa_id and rol in ("empresa", "auditor")) else None
    asignar = [int(x) for x in empresas_analista if x] if rol == "analista" else []
    try:
        with db.scope_conn(scope_of(user)) as conn:
            nuevo = conn.execute(text(
                "INSERT INTO usuario (email,nombre,password_hash,rol_id,empresa_id,activo,debe_cambiar_pass) "
                "VALUES (:em,:no,:ph,(SELECT id FROM rol WHERE codigo=:rc),:eid,true,true) RETURNING id"),
                {"em": email.strip().lower(), "no": nombre.strip(),
                 "ph": hash_password(password), "rc": rol, "eid": eid}).scalar()
            for e_id in asignar:
                conn.execute(text(
                    "INSERT INTO usuario_empresa(usuario_id,empresa_id) VALUES (:u,:e) "
                    "ON CONFLICT DO NOTHING"), {"u": nuevo, "e": e_id})
    except Exception as e:
        return RedirectResponse(f"/usuarios?err=No+se+pudo+crear+({type(e).__name__})", status_code=303)
    detalle = f"{email} ({rol})" + (f" · {len(asignar)} empresa(s)" if asignar else "")
    db.audit(scope_of(user), "crear_usuario", "usuario", eid, detalle)
    return RedirectResponse("/usuarios?msg=Credencial+emitida+(cambio+obligatorio):+" + email, status_code=303)


@app.post("/usuarios/{uid}/password")
def usuarios_reset_password(request: Request, uid: int,
                            password: str = Form(...), csrf: str = Form("")):
    """El administrador restablece la contraseña de un usuario (cambio obligatorio)."""
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_usuarios"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    problemas = password_issues(password)
    if problemas:
        return RedirectResponse("/usuarios?err=Contraseña+débil:+" + ", ".join(problemas).replace(" ", "+"),
                                status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            correo = conn.execute(text(
                "UPDATE usuario SET password_hash=:ph, debe_cambiar_pass=true "
                "WHERE id=:u RETURNING email"),
                {"ph": hash_password(password), "u": uid}).scalar()
    except Exception as e:
        return RedirectResponse(f"/usuarios?err=No+se+pudo+restablecer+({type(e).__name__})", status_code=303)
    if not correo:
        return RedirectResponse("/usuarios?err=Usuario+no+encontrado", status_code=303)
    db.audit(scope_of(user), "reset_password", "usuario", None, correo)
    return RedirectResponse("/usuarios?msg=Contraseña+restablecida+(cambio+obligatorio):+" + correo,
                            status_code=303)


@app.post("/usuarios/{uid}/empresas")
def usuarios_asignar_empresas(request: Request, uid: int,
                              empresas_analista: list[str] = Form([]), csrf: str = Form("")):
    """Reemplaza el conjunto de empresas asignadas a un analista (vacío = todas)."""
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_usuarios"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    ids = [int(x) for x in empresas_analista if x]
    try:
        with db.scope_conn(scope_of(user)) as conn:
            fila = conn.execute(text(
                "SELECT u.email, r.codigo AS rol FROM usuario u JOIN rol r ON r.id=u.rol_id "
                "WHERE u.id=:u"), {"u": uid}).mappings().first()
            if not fila:
                return RedirectResponse("/usuarios?err=Usuario+no+encontrado", status_code=303)
            if fila["rol"] != "analista":
                return RedirectResponse(
                    "/usuarios?err=Solo+los+analistas+se+asignan+a+varias+empresas", status_code=303)
            conn.execute(text("DELETE FROM usuario_empresa WHERE usuario_id=:u"), {"u": uid})
            for e_id in ids:
                conn.execute(text(
                    "INSERT INTO usuario_empresa(usuario_id,empresa_id) VALUES (:u,:e) "
                    "ON CONFLICT DO NOTHING"), {"u": uid, "e": e_id})
    except Exception as e:
        return RedirectResponse(f"/usuarios?err=No+se+pudo+asignar+({type(e).__name__})", status_code=303)
    cuantas = "todas" if not ids else str(len(ids))
    db.audit(scope_of(user), "asignar_empresas", "usuario", None, f'{fila["email"]} → {cuantas}')
    return RedirectResponse(
        f"/usuarios?msg=Empresas+asignadas+({cuantas})+a+{fila['email']}", status_code=303)


# ------------------------------------------------------------------ operación mensual
@app.get("/empresa/{eid}/mensual", response_class=HTMLResponse)
def mensual(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        serie = ops.tablero(conn, eid)
        meses_fac = ops.meses_con_factura(conn, eid)
        sel = request.query_params.get("fmes")
        fsel = None
        if meses_fac:
            fsel = meses_fac[-1]
            if sel:
                for (a, m) in meses_fac:
                    if f"{a}-{m}" == sel:
                        fsel = (a, m)
                        break
        factura = ops.tablero_factura(conn, eid, fsel[0], fsel[1]) if fsel else {}
    return tpl.TemplateResponse(request, "mensual.html", _ctx(
        request, emp=emp, serie=serie, meses=ops.MESES, gatillo=ops.GATILLO,
        clases=ops.CLASES, factura=factura, meses_fac=meses_fac, fsel=fsel,
        puede_cargar=rbac.can(user, "cargar_mensual"),
        puede_procesar=rbac.can(user, "procesar_indexacion")))


@app.post("/empresa/{eid}/carga")
def cargar(request: Request, eid: int, anio: int = Form(...), mes: int = Form(...),
           servicio: str = Form(...), suscriptores: str = Form(""), m3: str = Form(""),
           facturacion: str = Form(""), novedades: str = Form(""),
           origen: str = Form("archivo_propio"), next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/mensual"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)

    def _num(x):
        x = (x or "").strip().replace(",", ".")
        return float(x) if x else None

    try:
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO carga_mensual(empresa_id,anio,mes,servicio,suscriptores,m3_facturados,"
                " facturacion,novedades,origen,cargado_por) "
                "VALUES (:e,:a,:m,:s,:su,:m3,:fa,:nv,:og,:up) "
                "ON CONFLICT (empresa_id,anio,mes,servicio) DO UPDATE SET "
                " suscriptores=excluded.suscriptores, m3_facturados=excluded.m3_facturados, "
                " facturacion=excluded.facturacion, novedades=excluded.novedades, "
                " origen=excluded.origen, cargado_por=excluded.cargado_por, cargado_en=now()"),
                {"e": eid, "a": anio, "m": mes, "s": servicio,
                 "su": int(_num(suscriptores)) if _num(suscriptores) is not None else None,
                 "m3": _num(m3), "fa": _num(facturacion), "nv": novedades.strip() or None,
                 "og": origen, "up": user["user_id"]})
    except Exception as e:
        return RedirectResponse(_dest(next, dflt, f"err=No+se+pudo+cargar+({type(e).__name__})"),
                                status_code=303)
    db.audit(scope_of(user), "carga_mensual", "empresa", eid, f"{ops.MESES.get(mes,mes)}-{anio} {servicio}")
    return RedirectResponse(_dest(next, dflt, "msg=Carga+registrada"), status_code=303)


@app.post("/empresa/{eid}/carga-agua")
def cargar_agua(request: Request, eid: int, anio: int = Form(...), mes: int = Form(...),
                servicio: str = Form(...), punto: str = Form(...), m3_producido: str = Form(""),
                m3_bloque_entregado: str = Form(""), m3_bloque_recibido: str = Form(""),
                origen: str = Form("propio"), next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=agua"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)

    def _num(x):
        x = (x or "").strip().replace(",", ".")
        return float(x) if x else None

    if not (punto or "").strip():
        return RedirectResponse(_dest(next, dflt, "err=Indique+el+punto+de+macromedición"), status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
            if not emp:
                return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
            conn.execute(text(
                "INSERT INTO macromedicion(empresa_id,anio,mes,servicio,punto,m3_producido,"
                " m3_bloque_entregado,m3_bloque_recibido,origen,cargado_por) "
                "VALUES (:e,:a,:m,:s,:p,:mp,:be,:br,:og,:up) "
                "ON CONFLICT (empresa_id,anio,mes,servicio,punto) DO UPDATE SET "
                " m3_producido=excluded.m3_producido, m3_bloque_entregado=excluded.m3_bloque_entregado, "
                " m3_bloque_recibido=excluded.m3_bloque_recibido, origen=excluded.origen, "
                " cargado_por=excluded.cargado_por, cargado_en=now()"),
                {"e": eid, "a": anio, "m": mes, "s": servicio, "p": punto.strip(),
                 "mp": _num(m3_producido), "be": _num(m3_bloque_entregado),
                 "br": _num(m3_bloque_recibido), "og": origen.strip() or "propio", "up": user["user_id"]})
    except Exception as e:
        return RedirectResponse(_dest(next, dflt, f"err=No+se+pudo+cargar+({type(e).__name__})"), status_code=303)
    db.audit(scope_of(user), "carga_agua", "empresa", eid, f"{ops.MESES.get(mes,mes)}-{anio} {servicio} {punto.strip()}")
    return RedirectResponse(_dest(next, dflt, "msg=Macromedición+registrada"), status_code=303)


@app.post("/empresa/{eid}/procesar")
def procesar(request: Request, eid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "procesar_indexacion"):
        return RedirectResponse(f"/empresa/{eid}/mensual?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        filas, ix = ops.procesar_empresa(conn, eid)
        fac = ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "procesar_indexacion", "empresa", eid, f"{filas} meses, {ix} indexaciones, {fac} factura")
    return RedirectResponse(
        f"/empresa/{eid}/mensual?msg=Indexación+procesada+({filas}+meses,+{ix}+indexaciones);+factura+por+estrato:+{fac}+filas",
        status_code=303)


@app.post("/empresa/{eid}/cargar-csv")
def cargar_csv(request: Request, eid: int, tipo: str = Form(...),
               archivos: list[UploadFile] = File(..., alias="archivos"),
               next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/mensual"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    if tipo not in ingesta.TIPOS:
        return RedirectResponse(_dest(next, dflt, "err=Tipo+inválido"), status_code=303)
    tot_ok, errs, n_arch = 0, [], 0
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        for arch in archivos:
            if not getattr(arch, "filename", ""):
                continue
            ok, err = ingesta.TIPOS[tipo](conn, eid, _leer_csv(arch))
            tot_ok += ok; errs += (err or []); n_arch += 1
        if tipo in ("comercial", "factores") and tot_ok:
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargar_csv", "empresa", eid, f"{tipo}: {n_arch} archivos, {tot_ok} filas, {len(errs)} errores")
    aviso = f"msg={tipo}:+{n_arch}+archivo(s),+{tot_ok}+filas+cargadas"
    if errs:
        aviso += ";+" + ",+".join(errs[:3]).replace(" ", "+") + ("+…" if len(errs) > 3 else "")
    return RedirectResponse(_dest(next, dflt, aviso), status_code=303)


@app.post("/empresa/{eid}/cargar-sui-lote")
async def cargar_sui_lote(request: Request, eid: int):
    """Carga varios reportes ORIGINALES del SUI a la vez (p. ej. los 12 meses de un año
    y servicio). Cada archivo se procesa con su mes; el año y el servicio son comunes al lote."""
    if (r := _need_login(request)):
        return r
    form = await request.form()
    if (bad := _bad_csrf(request, form.get("csrf"))):
        return bad
    user = session_user(request)
    nxt = form.get("next") or f"/empresa/{eid}/cargar?fuente=comercial"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(nxt, nxt, "err=No+autorizado"), status_code=303)
    servicio = form.get("servicio") or "acueducto"
    try:
        anio = int(form.get("anio"))
    except (TypeError, ValueError):
        return RedirectResponse(_dest(nxt, nxt, "err=Año+inválido"), status_code=303)
    archivos = form.getlist("archivos")
    meses = form.getlist("mes")
    n_ok, clases, errores = 0, 0, []
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        for i, arch in enumerate(archivos):
            fn = getattr(arch, "filename", "")
            if not fn:
                continue
            mes_raw = meses[i] if i < len(meses) else ""
            try:
                mes = int(mes_raw)
                assert 1 <= mes <= 12
            except (TypeError, ValueError, AssertionError):
                mes = ingesta.mes_de_nombre(fn)          # respaldo: deducir el mes del nombre
            if not mes:
                errores.append(f"{fn}:+sin+mes")
                continue
            ok, err = ingesta.cargar_facturacion_sui(conn, eid, servicio, anio, mes, _leer_csv(arch))
            if ok:
                n_ok += 1; clases += ok
            else:
                errores.append(f"{ops.MESES.get(mes,mes)}:+" + (err[0] if err else "sin+datos"))
        if n_ok:
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargar_sui_lote", "empresa", eid,
             f"{servicio} {anio}: {n_ok} meses, {clases} clases, {len(errores)} errores")
    aviso = f"msg=SUI+{servicio}+{anio}:+{n_ok}+mes(es)+cargados+({clases}+clases)"
    if errores:
        aviso += ";+" + ",+".join(errores[:3]).replace(" ", "+")
    return RedirectResponse(_dest(nxt, nxt, aviso), status_code=303)


@app.post("/empresa/{eid}/cargar-sui")
def cargar_sui(request: Request, eid: int, servicio: str = Form(...), anio: int = Form(...),
               mes: int = Form(...), archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/mensual?err=No+autorizado", status_code=303)
    contenido = _leer_csv(archivo)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        ok, err = ingesta.cargar_facturacion_sui(conn, eid, servicio, anio, mes, contenido)
        if ok:
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargar_sui", "empresa", eid,
             f"{servicio} {ops.MESES.get(mes,mes)}-{anio}: {ok} clases, {len(err)} errores")
    aviso = f"Facturación+SUI+({servicio}):+{ok}+clases+agregadas"
    if err:
        aviso += f";+" + ",+".join(err[:2]).replace(" ", "+")
    return RedirectResponse(f"/empresa/{eid}/mensual?msg={aviso}", status_code=303)


@app.get("/empresa/{eid}/recalculo", response_class=HTMLResponse)
def recalculo(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        serie = rc.tablero(conn, eid)
        tiene_base = bool(rc.base_params(conn, eid))
        ipuf = rc.ipuf_estrella(conn, eid)
    return tpl.TemplateResponse(request, "recalculo.html", _ctx(
        request, emp=emp, serie=serie, meses=ops.MESES, ipuf=ipuf, tiene_base=tiene_base,
        puede_cargar=rbac.can(user, "cargar_mensual"),
        puede_procesar=rbac.can(user, "procesar_indexacion")))


@app.post("/empresa/{eid}/recalcular-mes")
def recalcular_mes(request: Request, eid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "procesar_indexacion"):
        return RedirectResponse(f"/empresa/{eid}/recalculo?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        filas = rc.recalcular(conn, eid)
    db.audit(scope_of(user), "recalcular_mensual", "empresa", eid, f"{filas} meses-servicio")
    return RedirectResponse(
        f"/empresa/{eid}/recalculo?msg=Recálculo+mensual+procesado+({filas}+filas)", status_code=303)


def _catalogo_path(codigo):
    import os as _os
    nombre = f"catalogo_clasificacion_{codigo.lower().replace('_','')}.csv"
    p = _os.path.join(config.BASE_DIR, "catalogos", nombre)
    return p if _os.path.exists(p) else None


@app.post("/empresa/{eid}/cargar-balance")
def cargar_balance(request: Request, eid: int, anio: int = Form(...),
                   mes_ini: int = Form(1), mes_fin: int = Form(12), mes: int = Form(None),
                   archivo: UploadFile = File(...), next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/recalculo"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    # compatibilidad: si llega 'mes' suelto, es un solo mes
    if mes is not None:
        mes_ini = mes_fin = mes
    mes_ini = max(1, min(12, int(mes_ini)))
    mes_fin = max(1, min(12, int(mes_fin)))
    if mes_ini > mes_fin:
        mes_ini, mes_fin = mes_fin, mes_ini
    n_meses = mes_fin - mes_ini + 1
    import os as _os, tempfile
    raw = archivo.file.read()
    nombre = (archivo.filename or "").lower()
    try:
        if nombre.endswith((".xlsx", ".xlsm")):
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
                tf.write(raw); tmp = tf.name
            filas, _hr, _cols = lb.leer_xlsx(tmp)
            _os.unlink(tmp)
        else:
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    texto = raw.decode(enc); break
                except UnicodeDecodeError:
                    texto = None
            filas, _hr, _cols = lb.leer_csv(texto or raw.decode("latin-1"))
    except Exception as e:
        return RedirectResponse(
            _dest(next, dflt, f"err=No+se+pudo+leer+el+balance+({type(e).__name__})"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT codigo FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        cat_path = _catalogo_path(emp["codigo"])
        if not cat_path:
            return RedirectResponse(
                _dest(next, dflt, "err=Falta+el+catálogo+de+clasificación+de+esta+empresa"),
                status_code=303)
        catalogo = clf.cargar_catalogo(open(cat_path, encoding="utf-8").read())
        sub, comp, sin = clf.clasificar(filas, catalogo)
        nums = clf.numeradores(sub)
        split = rc.split_servicio(conn, eid)
        # El balance subido corresponde al rango elegido; se reparte por igual entre sus meses,
        # de modo que la suma del período reproduce el balance cargado.
        nums_mes = {k: (float(v or 0.0) / n_meses) for k, v in nums.items()}
        n = 0
        for m in range(mes_ini, mes_fin + 1):
            n += ingesta.persistir_numeradores_mensual(conn, eid, anio, m, nums_mes, split)
        rc.recalcular(conn, eid)
    rango = (ops.MESES.get(mes_ini, mes_ini) if n_meses == 1
             else f"{ops.MESES.get(mes_ini, mes_ini)}–{ops.MESES.get(mes_fin, mes_fin)}")
    db.audit(scope_of(user), "cargar_balance", "empresa", eid,
             f"{rango}-{anio} ({n_meses} mes/es): {n} numeradores, {len(sin)} cuentas sin clasificar")
    aviso = (f"msg=Balance+{rango}-{anio}:+distribuido+en+{n_meses}+mes(es),+"
             f"numeradores+clasificados+y+recálculo+hecho")
    if sin:
        aviso += f";+{len(sin)}+cuentas+sin+clasificar"
    return RedirectResponse(_dest(next, dflt, aviso), status_code=303)


@app.get("/empresa/{eid}/inversiones", response_class=HTMLResponse)
def inversiones(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    sec = request.query_params.get("sec") or "agua"
    if sec not in ("agua", "bcr", "poir", "activos", "provision"):
        sec = "agua"
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        proyectos = inv.tablero(conn, eid)
        res = inv.resumen(conn, eid)
        servicios = [s for s, on in (("acueducto", emp["presta_ac"]), ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
        bcr_activos = bcr.lista(conn, eid)
        r_emp = float(emp["r"]) if emp["r"] is not None else 0.0903
        bcr0 = bcr.bcr0_calculo(conn, eid, r_emp)
        bcr_params = bcr.params(conn, eid)
        bcr_series = bcr.serie_list(conn, eid)
        bcr_ingresos = {s: bcr.ingresos_vp(conn, eid, s) for s in servicios}
        bcr_mods = {s: poir.mods_list(conn, eid, s) for s in servicios}
        bcr_cmi = {s: poir.resumen_cmi(conn, eid, s) for s in servicios}
        cumpl = bcr.cumplimiento(conn, eid)
        proy = {s: bcr.proyeccion(conn, eid, s, r_emp) for s in servicios}
    return tpl.TemplateResponse(request, "inversiones.html", _ctx(
        request, emp=emp, proyectos=proyectos, resumen=res, sec=sec,
        clasificaciones=inv.CLASIFICACIONES, estados=inv.ESTADOS,
        comp_ac=inv.COMPONENTES_AC, comp_al=inv.COMPONENTES_AL,
        servicios=servicios, bcr_activos=bcr_activos, bcr0=bcr0, bcr_comp=bcr.COMPONENTES,
        bcr_serv=bcr.SERVICIOS, bcr_params=bcr_params, bcr_series=bcr_series, bcr_ingresos=bcr_ingresos,
        bcr_mods=bcr_mods, bcr_cmi=bcr_cmi, cumpl=cumpl, proy=proy, r_emp=r_emp,
        puede_cargar=rbac.can(user, "cargar_mensual")))


def _fnum(x):
    x = (x or "").strip().replace(",", ".")
    try:
        return float(x) if x != "" else None
    except ValueError:
        return None


@app.post("/empresa/{eid}/inversion-nueva")
def inversion_nueva(request: Request, eid: int, codigo_poir: str = Form(...),
                    nombre: str = Form(...), servicio: str = Form(...), aps: str = Form(""),
                    componente_sistema: str = Form(""), meta_asociada: str = Form(""),
                    clasificacion: str = Form("CMI_POIR"), origen: str = Form("POIR_nuevo"),
                    valor_planeado: str = Form(""), fecha_planeada_operacion: str = Form(""),
                    via688: str = Form(""), vp_recaudo: str = Form(""), vida_util: str = Form(""),
                    observacion: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/inversiones?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        pid, err = inv.crear_proyecto(conn, eid, {
            "codigo_poir": codigo_poir, "nombre": nombre, "servicio": servicio, "aps": aps,
            "componente_sistema": componente_sistema, "meta_asociada": meta_asociada,
            "clasificacion": clasificacion, "origen": origen,
            "valor_planeado": _fnum(valor_planeado),
            "fecha_planeada_operacion": fecha_planeada_operacion.strip() or None,
            "via688": _fnum(via688), "vp_recaudo": _fnum(vp_recaudo),
            "vida_util": _fnum(vida_util), "observacion": observacion.strip() or None,
            "creado_por": user["user_id"]})
    if err:
        return RedirectResponse(f"/empresa/{eid}/inversiones?err=" + err.replace(" ", "+"),
                                status_code=303)
    db.audit(scope_of(user), "crear_proyecto", "empresa", eid, f"POIR {codigo_poir}")
    return RedirectResponse(f"/empresa/{eid}/inversiones?msg=Proyecto+{codigo_poir}+guardado",
                            status_code=303)


@app.post("/empresa/{eid}/inversion-avance")
def inversion_avance(request: Request, eid: int, proyecto_id: int = Form(...),
                     anio: int = Form(...), mes: int = Form(...), avance_fisico: str = Form(""),
                     avance_financiero: str = Form(""), fecha_real_operacion: str = Form(""),
                     observacion: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/inversiones?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        ok, err = inv.registrar_avance(conn, eid, proyecto_id, anio, mes,
                                       _fnum(avance_fisico), _fnum(avance_financiero),
                                       observacion.strip() or None,
                                       fecha_real_operacion.strip() or None, user["user_id"])
    if not ok:
        return RedirectResponse(f"/empresa/{eid}/inversiones?err=" + (err or "no+se+pudo").replace(" ", "+"),
                                status_code=303)
    db.audit(scope_of(user), "registrar_avance", "empresa", eid,
             f"proyecto {proyecto_id} {ops.MESES.get(mes,mes)}-{anio}")
    return RedirectResponse(f"/empresa/{eid}/inversiones?msg=Avance+registrado", status_code=303)


# ------------------------------------------------------------------ tablero de indicadores
@app.get("/empresa/{eid}/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        datos = dash.resumen(conn, eid)
    return tpl.TemplateResponse(request, "dashboard.html", _ctx(
        request, emp=emp, d=datos, meses=ops.MESES))


# ------------------------------------------------------------------ balance de subsidios y contribuciones (FSRI)
@app.get("/empresa/{eid}/subsidios", response_class=HTMLResponse)
def subsidios(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        anios = subs.anios_disponibles(conn, eid)
        sel = request.query_params.get("anio")
        anio = anios[0] if anios else None
        if sel and sel.isdigit() and int(sel) in anios:
            anio = int(sel)
        bal = subs.balance(conn, eid, anio)
    return tpl.TemplateResponse(request, "subsidios.html", _ctx(
        request, emp=emp, bal=bal, anios=anios, anio=anio, meses=ops.MESES))


# ------------------------------------------------------------------ Configuración del APS (art. 2.1.2.1.1.5)
@app.get("/empresa/{eid}/aps", response_class=HTMLResponse)
def aps_config(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        res = aps.resumen(conn, eid)
        sel = request.query_params.get("mun")
        if not sel and res["items"]:
            sel = res["items"][0]["cod_dane"]        # primer municipio por defecto
        actual, archivos = None, []
        if sel:
            actual = aps.obtener(conn, eid, sel)
            if actual:
                archivos = aps.archivos(conn, eid, actual["id"])
    return tpl.TemplateResponse(request, "aps.html", _ctx(
        request, emp=emp, res=res, sel=sel, actual=dict(actual) if actual else None,
        archivos=archivos, SERVICIOS=aps.SERVICIOS, ZONAS=aps.ZONAS,
        SISTEMA_RURAL=aps.SISTEMA_RURAL, INTERCONEXION=aps.INTERCONEXION,
        TIPO_REGIONAL=aps.TIPO_REGIONAL, INSTRUMENTOS_OT=aps.INSTRUMENTOS_OT,
        CATEGORIAS=aps.CATEGORIAS_ARCHIVO, EXT=sorted(aps.EXT_PERMITIDAS),
        puede_editar=rbac.can(user, "cargar_mensual")))


@app.post("/empresa/{eid}/aps/guardar")
async def aps_guardar(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    form = await request.form()
    if (bad := _bad_csrf(request, form.get("csrf"))):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/aps?err=No+autorizado", status_code=303)
    cod = (form.get("cod_dane") or "").strip()

    def _b(n):
        return form.get(n) is not None
    def _i(n):
        v = "".join(ch for ch in (form.get(n) or "") if ch.isdigit())
        return int(v) if v else None
    def _txt(n):
        return (form.get(n) or "").strip() or None

    d = {
        "numero_aps": _i("numero_aps"), "nombre": _txt("nombre"), "codigo_aps": _txt("codigo_aps"),
        "servicios": form.get("servicios") or "ambos",
        "aps_difiere_servicios": _b("aps_difiere_servicios"),
        "zona": form.get("zona") or "urbana", "sistema_rural": form.get("sistema_rural") or "na",
        "esquema_regional": _b("esquema_regional"),
        "sistema_interconexion": form.get("sistema_interconexion") or "na",
        "tipo_regional": form.get("tipo_regional") or "na",
        "mercado_regional_declarado": _b("mercado_regional_declarado"),
        "aplicaba_825": _b("aplicaba_825"), "menor_5000": _b("menor_5000"),
        "pdet": _b("pdet"), "zomac": _b("zomac"),
        "ed_particular": _b("ed_particular"), "ed_urbano_zdu": _b("ed_urbano_zdu"),
        "ed_rural_zrni": _b("ed_rural_zrni"), "toma_posesion_sspd": _b("toma_posesion_sspd"),
        "georref_sistema": _txt("georref_sistema") or "MAGNA-SIRGAS",
        "georref_presentada": _b("georref_presentada"), "area_ha": _fnum(form.get("area_ha")),
        "instrumento_ot": _txt("instrumento_ot"), "instrumento_ot_acto": _txt("instrumento_ot_acto"),
        "pmaa": _b("pmaa"), "reportado_municipio": _b("reportado_municipio"),
        "reportado_fecha": _txt("reportado_fecha"), "reportado_acto": _txt("reportado_acto"),
        "observacion": _txt("observacion"),
    }
    try:
        with db.scope_conn(scope_of(user)) as conn:
            _aid, err = aps.guardar(conn, eid, cod, d, user["user_id"])
        if err:
            return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=" + err.replace(" ", "+"),
                                    status_code=303)
    except Exception as e:
        return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=No+se+pudo+guardar+({type(e).__name__})",
                                status_code=303)
    db.audit(scope_of(user), "aps_guardar", "empresa", eid, cod)
    return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&msg=APS+guardada", status_code=303)


@app.post("/empresa/{eid}/aps/archivo")
def aps_archivo_subir(request: Request, eid: int, cod_dane: str = Form(...),
                      categoria: str = Form("soporte_general"),
                      archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/aps?err=No+autorizado", status_code=303)
    cod = (cod_dane or "").strip()
    raw = archivo.file.read()
    nombre = (archivo.filename or "archivo").strip()
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in aps.EXT_PERMITIDAS:
        return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=Formato+no+admitido+({ext})",
                                status_code=303)
    if len(raw) > aps.MAX_BYTES:
        return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=Archivo+supera+25+MB", status_code=303)
    if categoria not in aps.CATEGORIAS_ARCHIVO:
        categoria = "soporte_general"
    try:
        with db.scope_conn(scope_of(user)) as conn:
            a = aps.obtener(conn, eid, cod)
            if a:
                a_id = a["id"]
            else:
                a_id, err = aps.guardar(conn, eid, cod, {}, user["user_id"])  # crea el APS con valores por defecto
                if err:
                    return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=" + err.replace(" ", "+"),
                                            status_code=303)
            aps.guardar_archivo(conn, eid, a_id, categoria, nombre, ext, raw, user["user_id"])
    except Exception as e:
        return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&err=No+se+pudo+subir+({type(e).__name__})",
                                status_code=303)
    db.audit(scope_of(user), "aps_archivo", "empresa", eid, f"{cod}:{categoria}:{nombre}")
    return RedirectResponse(f"/empresa/{eid}/aps?mun={cod}&msg=Soporte+cargado", status_code=303)


@app.get("/empresa/{eid}/aps/archivo/{aid}")
def aps_archivo_bajar(request: Request, eid: int, aid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        f = aps.archivo(conn, eid, aid)
    if not f:
        return RedirectResponse(f"/empresa/{eid}/aps?err=Archivo+no+disponible", status_code=303)
    import mimetypes
    media = mimetypes.guess_type(f["nombre"] or "")[0] or "application/octet-stream"
    seguro = (f["nombre"] or "archivo").replace('"', "")
    return Response(content=bytes(f["contenido"]), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{seguro}"'})


@app.post("/empresa/{eid}/aps/archivo/{aid}/eliminar")
def aps_archivo_eliminar(request: Request, eid: int, aid: int,
                         cod_dane: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/aps?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        aps.eliminar_archivo(conn, eid, aid)
    db.audit(scope_of(user), "aps_archivo_eliminar", "empresa", eid, f"{cod_dane}:{aid}")
    return RedirectResponse(f"/empresa/{eid}/aps?mun={cod_dane.strip()}&msg=Soporte+eliminado", status_code=303)


# ------------------------------------------------------------------ Actualización de costos (indexación 3 %)
ANIOS_TAR = {2026: "Período de inicio (jul–dic 2026)", 2027: "Primer año tarifario (2027)"}


def _emp_or_redirect(conn, eid):
    return conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()


@app.get("/empresa/{eid}/actualizacion", response_class=HTMLResponse)
def actualizacion(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        serie = ops.tablero(conn, eid)
    resumen = {}
    for serv, rows in serie.items():
        if not rows:
            continue
        ult = rows[-1]
        resumen[serv] = {
            "cf": ult["cargo_fijo"], "cc": ult["cargo_consumo"],
            "var_ipcs": ult["variacion_acum"], "var_ipc": ult["var_ipc"],
            "anio": ult["anio"], "mes": ult["mes"]}
    return tpl.TemplateResponse(request, "actualizacion.html", _ctx(
        request, emp=emp, serie=serie, resumen=resumen, gatillo=ops.GATILLO, meses=ops.MESES))


# ------------------------------------------------------------------ Validación de información por año tarifario
@app.get("/empresa/{eid}/validacion", response_class=HTMLResponse)
def validacion(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        apsres = aps.resumen(conn, eid)

        def _por_anio(sql):
            return dict(conn.execute(text(sql), {"e": eid}).all())
        com = _por_anio("SELECT anio, count(DISTINCT (mes,servicio)) FROM carga_mensual WHERE empresa_id=:e GROUP BY anio")
        bal = _por_anio("SELECT anio, count(DISTINCT (mes,servicio)) FROM numerador_mensual WHERE empresa_id=:e GROUP BY anio")
        agua = _por_anio("SELECT anio, count(DISTINCT (mes,servicio)) FROM macromedicion WHERE empresa_id=:e GROUP BY anio")
        fsub = _por_anio("SELECT vigencia AS anio, count(*) FROM factor_subsidio WHERE empresa_id=:e GROUP BY vigencia")
    n_serv = (1 if emp["presta_ac"] else 0) + (1 if emp["presta_al"] else 0) or 1
    # El período de inicio se calcula con la línea base 2024–2025 (dos años completos).
    anios = per.PERIODOS[0]["anios_base"]              # [2024, 2025]
    esperado = {a: 12 * n_serv for a in anios}          # 12 meses × servicios por año base
    anios_tar = {a: str(a) for a in anios}
    fuentes = [
        {"clave": "aps", "nombre": "Configuración del APS", "general": True,
         "valor": f"{apsres['n_completos']}/{apsres['n_municipios']} completos",
         "ok": apsres["n_municipios"] > 0 and apsres["n_completos"] == apsres["n_municipios"]},
        {"clave": "comercial", "nombre": "Comercial (suscriptores y consumos)", "datos": com},
        {"clave": "balance", "nombre": "Balance de prueba (numeradores CMO/CMI/CMICT)", "datos": bal},
        {"clave": "agua", "nombre": "Agua producida / macromedición", "datos": agua},
        {"clave": "subsidios", "nombre": "Factores de subsidio y contribución", "datos": fsub, "por_registro": True},
        {"clave": "costos_part", "nombre": "Costos particulares (art. Res. 1032)", "pendiente": True},
    ]
    return tpl.TemplateResponse(request, "validacion.html", _ctx(
        request, emp=emp, fuentes=fuentes, anios=anios, esperado=esperado,
        anios_tar=anios_tar, n_serv=n_serv))


# ------------------------------------------------------------------ Resultados · Evolución de costos y tarifa
@app.get("/empresa/{eid}/evolucion", response_class=HTMLResponse)
def evolucion(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        serie = ops.tablero(conn, eid)
    return tpl.TemplateResponse(request, "evolucion.html", _ctx(
        request, emp=emp, serie=serie, meses=ops.MESES))


# ------------------------------------------------------------------ Resultados · Simulador tarifario
@app.get("/empresa/{eid}/simulador", response_class=HTMLResponse)
def simulador(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    try:
        consumo = float((request.query_params.get("consumo") or "16").replace(",", "."))
    except ValueError:
        consumo = 16.0
    basico = 16.0   # consumo básico de referencia (m³/suscriptor·mes)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        tarifas = conn.execute(text(
            "SELECT DISTINCT ON (servicio) servicio, cargo_fijo, cargo_consumo, anio, mes "
            "FROM tarifa_vigente WHERE empresa_id=:e ORDER BY servicio, anio DESC, mes DESC"),
            {"e": eid}).mappings().all()
        factores = conn.execute(text(
            "SELECT DISTINCT ON (servicio, clase) servicio, clase, factor_cargofijo, factor_consumo "
            "FROM factor_subsidio WHERE empresa_id=:e ORDER BY servicio, clase, vigencia DESC"),
            {"e": eid}).mappings().all()
    tar = {t["servicio"]: t for t in tarifas}
    fac = {(f["servicio"], f["clase"]): f for f in factores}
    m3s = min(consumo, basico)
    resto = max(consumo - basico, 0.0)
    filas = []
    for clase, nombre in ops.CLASES.items():
        fila = {"clase": clase, "nombre": nombre, "serv": {}, "total": 0.0, "total_pleno": 0.0}
        hay = False
        for serv, t in tar.items():
            CF = float(t["cargo_fijo"] or 0.0)
            CC = float(t["cargo_consumo"] or 0.0)
            f = fac.get((serv, clase))
            fcf = float(f["factor_cargofijo"]) if f and f["factor_cargofijo"] is not None else 0.0
            fcc = float(f["factor_consumo"]) if f and f["factor_consumo"] is not None else 0.0
            cf_fact = CF * (1 + fcf)
            cc_fact = CC * (m3s * (1 + fcc) + resto)
            pleno = CF + CC * consumo
            fila["serv"][serv] = {"cf": cf_fact, "cc": cc_fact, "total": cf_fact + cc_fact, "pleno": pleno,
                                  "fcf": fcf, "fcc": fcc, "tiene_factor": f is not None}
            fila["total"] += cf_fact + cc_fact
            fila["total_pleno"] += pleno
            hay = True
        if hay:
            filas.append(fila)
    return tpl.TemplateResponse(request, "simulador.html", _ctx(
        request, emp=emp, filas=filas, consumo=consumo, basico=basico,
        servicios=list(tar.keys()), hay_tarifa=bool(tar)))


# ------------------------------------------------------------------ Resultados · Suficiencia financiera
@app.get("/empresa/{eid}/suficiencia", response_class=HTMLResponse)
def suficiencia(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        # Facturación teórica del último mes con tarifa, por servicio
        filas = conn.execute(text(
            "SELECT tv.servicio, tv.anio, tv.mes, tv.cargo_fijo, tv.cargo_consumo, "
            "       cm.suscriptores, cm.m3_facturados "
            "FROM tarifa_vigente tv "
            "LEFT JOIN carga_mensual cm ON cm.empresa_id=tv.empresa_id AND cm.anio=tv.anio "
            "     AND cm.mes=tv.mes AND cm.servicio=tv.servicio "
            "WHERE tv.empresa_id=:e AND (tv.anio,tv.mes) = ("
            "   SELECT anio,mes FROM tarifa_vigente WHERE empresa_id=:e ORDER BY anio DESC, mes DESC LIMIT 1) "
            "ORDER BY tv.servicio"), {"e": eid}).mappings().all()
    serv = []
    tot_ing = 0.0
    for r0 in filas:
        CF = float(r0["cargo_fijo"] or 0.0); CC = float(r0["cargo_consumo"] or 0.0)
        susc = r0["suscriptores"] or 0; m3 = float(r0["m3_facturados"] or 0.0)
        ingreso = CF * susc + CC * m3
        tot_ing += ingreso
        serv.append({"servicio": r0["servicio"], "anio": r0["anio"], "mes": r0["mes"],
                     "cf": CF, "cc": CC, "susc": susc, "m3": m3, "ingreso": ingreso,
                     "tiene_cantidades": susc or m3})
    return tpl.TemplateResponse(request, "suficiencia.html", _ctx(
        request, emp=emp, serv=serv, tot_ing=tot_ing, meses=ops.MESES))


# ------------------------------------------------------------------ Menú único «Cargar información»
@app.get("/empresa/{eid}/cargar", response_class=HTMLResponse)
def cargar_info(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    fuente = request.query_params.get("fuente") or "comercial"
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        com = conn.execute(text(
            "SELECT anio, mes, servicio, suscriptores, m3_facturados, origen FROM carga_mensual "
            "WHERE empresa_id=:e ORDER BY anio DESC, mes DESC, servicio"), {"e": eid}).mappings().all()
        bal = conn.execute(text(
            "SELECT anio, mes, servicio, count(*) AS n, sum(valor) AS total FROM numerador_mensual "
            "WHERE empresa_id=:e GROUP BY anio, mes, servicio ORDER BY anio DESC, mes DESC, servicio"),
            {"e": eid}).mappings().all()
        agua = conn.execute(text(
            "SELECT anio, mes, servicio, count(*) AS puntos, sum(m3_producido) AS m3 FROM macromedicion "
            "WHERE empresa_id=:e GROUP BY anio, mes, servicio ORDER BY anio DESC, mes DESC, servicio"),
            {"e": eid}).mappings().all()
        costos = cpart.lista(conn, eid)
        ajuste_coc = cpart.ajuste_coc(conn, eid)
        servicios_emp = [s for s, on in (("acueducto", emp["presta_ac"]), ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
        ccp_fap = {s: ccp.get(conn, eid, s) for s in servicios_emp}
    return tpl.TemplateResponse(request, "cargar.html", _ctx(
        request, emp=emp, fuente=fuente, com=com, bal=bal, agua=agua, costos=costos,
        ajuste_coc=ajuste_coc, ccp_fap=ccp_fap, servicios_emp=servicios_emp,
        ivh_opc=ccp.IVH_OPC, met_opc=ccp.MET_OPC,
        meses=ops.MESES, anios_tar=ANIOS_TAR, cat_cp=cpart.CATEGORIAS,
        serv_cp=cpart.SERVICIOS, periodos_carga=per.periodos_cargables(),
        puede_cargar=rbac.can(user, "cargar_mensual")))


@app.post("/empresa/{eid}/cargar-costo-particular")
def cargar_costo_particular(request: Request, eid: int, anio: int = Form(...),
                            servicio: str = Form("acueducto"), categoria: str = Form(""),
                            concepto: str = Form(...), valor: str = Form(""), unidad: str = Form(""),
                            cantidad: str = Form(""), precio_unitario: str = Form(""),
                            cuenta_contable: str = Form(""), valor_contable: str = Form(""),
                            origen: str = Form("empresa"), observacion: str = Form(""),
                            next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=costos"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            if not _emp_or_redirect(conn, eid):
                return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
            _cid, err = cpart.guardar(conn, eid, {
                "anio": anio, "servicio": servicio, "categoria": categoria, "concepto": concepto,
                "valor": _fnum(valor), "unidad": unidad, "cantidad": _fnum(cantidad),
                "precio_unitario": _fnum(precio_unitario), "cuenta_contable": cuenta_contable,
                "valor_contable": _fnum(valor_contable), "origen": origen,
                "observacion": observacion}, user["user_id"])
        if err:
            return RedirectResponse(_dest(next, dflt, "err=" + err.replace(" ", "+")), status_code=303)
    except Exception as e:
        return RedirectResponse(_dest(next, dflt, f"err=No+se+pudo+guardar+({type(e).__name__})"),
                                status_code=303)
    db.audit(scope_of(user), "costo_particular", "empresa", eid, f"{anio} {servicio}: {concepto}")
    return RedirectResponse(_dest(next, dflt, "msg=Costo+particular+guardado"), status_code=303)


@app.post("/empresa/{eid}/costo-particular/{cid}/eliminar")
def eliminar_costo_particular(request: Request, eid: int, cid: int,
                              next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=costos"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        cpart.eliminar(conn, eid, cid)
    db.audit(scope_of(user), "costo_particular_eliminar", "empresa", eid, str(cid))
    return RedirectResponse(_dest(next, dflt, "msg=Costo+particular+eliminado"), status_code=303)


@app.post("/empresa/{eid}/ccp-fap")
def ccp_fap_guardar(request: Request, eid: int, servicio: str = Form("acueducto"),
                    aplica: str = Form(None), ipuf_real: str = Form(""), ipuf_planeado: str = Form(""),
                    ivh: str = Form(""), metodologia: str = Form(""), cumplio: str = Form(""),
                    observacion: str = Form(""), next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=ccp"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    d = {"aplica": aplica is not None, "ipuf_real": _fnum(ipuf_real),
         "ipuf_planeado": _fnum(ipuf_planeado), "ivh": ivh or None, "metodologia": metodologia or None,
         "cumplio_meta": (True if cumplio == "si" else (False if cumplio == "no" else None)),
         "observacion": observacion}
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        fap, nota = ccp.set_fap(conn, eid, servicio, d)
    db.audit(scope_of(user), "ccp_fap", "empresa", eid, f"{servicio}: Fap={fap}")
    if fap is None:
        msg = "Fap+pendiente+(falta+información)"
    else:
        msg = ("Fap+" + servicio + "+=+" + ("%.2f" % fap).replace(".", ",")).replace(" ", "+")
    return RedirectResponse(_dest(next, dflt, "msg=" + msg), status_code=303)


# ------------------------------------------------------------------ Inventario de activos de la BCR
@app.post("/empresa/{eid}/bcr-activo")
def bcr_guardar(request: Request, eid: int, id: str = Form(""), servicio: str = Form(...),
                componente: str = Form(...), nombre: str = Form(...), valor_bruto: str = Form(""),
                plazo_remanente: str = Form(""), cuota_anual: str = Form(""),
                valor_pendiente: str = Form(""), origen: str = Form("BCR0"),
                observacion: str = Form(""), tipo_activo: str = Form(""), vida_util: str = Form(""),
                via688: str = Form(""), vp_cmi_q: str = Form(""), vpr0: str = Form(""),
                va0: str = Form(""), anio_poir: str = Form(""), ejecucion_real: str = Form(""),
                fecha_operacion: str = Form(""), next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            if not _emp_or_redirect(conn, eid):
                return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
            _aid, err = bcr.guardar(conn, eid, {
                "id": int(id) if (id or "").isdigit() else None, "servicio": servicio,
                "componente": componente, "nombre": nombre, "valor_bruto": _fnum(valor_bruto),
                "plazo_remanente": _fnum(plazo_remanente), "cuota_anual": _fnum(cuota_anual),
                "valor_pendiente": _fnum(valor_pendiente), "origen": origen,
                "observacion": observacion, "tipo_activo": tipo_activo, "vida_util": _fnum(vida_util),
                "via688": _fnum(via688), "vp_cmi_q": _fnum(vp_cmi_q), "vpr0": _fnum(vpr0),
                "va0": _fnum(va0), "anio_poir": int(anio_poir) if (anio_poir or "").strip().isdigit() else None,
                "ejecucion_real": _fnum(ejecucion_real), "fecha_operacion": fecha_operacion.strip() or None},
                user["user_id"])
        if err:
            return RedirectResponse(_dest(next, dflt, "err=" + err.replace(" ", "+")), status_code=303)
    except Exception as e:
        return RedirectResponse(_dest(next, dflt, f"err=No+se+pudo+guardar+({type(e).__name__})"),
                                status_code=303)
    db.audit(scope_of(user), "bcr_activo", "empresa", eid, f"{servicio} C{componente}: {nombre}")
    return RedirectResponse(_dest(next, dflt, "msg=Activo+de+la+BCR+guardado"), status_code=303)


@app.post("/empresa/{eid}/bcr-activo/{aid}/eliminar")
def bcr_eliminar(request: Request, eid: int, aid: int, next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        bcr.eliminar(conn, eid, aid)
    db.audit(scope_of(user), "bcr_activo_eliminar", "empresa", eid, str(aid))
    return RedirectResponse(_dest(next, dflt, "msg=Activo+eliminado"), status_code=303)


@app.post("/empresa/{eid}/bcr-param")
def bcr_param_guardar(request: Request, eid: int, servicio: str = Form(...), r688: str = Form(""),
                      ipc_dic_2014: str = Form(""), ipc_dic_2025: str = Form(""),
                      fecha_inicio_688: str = Form(""), provision_poir: str = Form(""),
                      ccp_2025: str = Form(""), observacion: str = Form(""),
                      next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        ok, err = bcr.param_set(conn, eid, servicio, {
            "r688": _fnum(r688), "ipc_dic_2014": _fnum(ipc_dic_2014), "ipc_dic_2025": _fnum(ipc_dic_2025),
            "fecha_inicio_688": fecha_inicio_688.strip() or None, "provision_poir": _fnum(provision_poir),
            "ccp_2025": _fnum(ccp_2025), "observacion": observacion})
    if err:
        return RedirectResponse(_dest(next, dflt, "err=" + err.replace(" ", "+")), status_code=303)
    db.audit(scope_of(user), "bcr_param", "empresa", eid, servicio)
    return RedirectResponse(_dest(next, dflt, "msg=Parámetros+688+guardados"), status_code=303)


@app.post("/empresa/{eid}/bcr-serie")
def bcr_serie_guardar(request: Request, eid: int, servicio: str = Form(...),
                      anio_tarifario: int = Form(...), q_m3: str = Form(""),
                      cmi_cobrado: str = Form(""), segmento: str = Form(""),
                      next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=agua"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    seg = "".join(ch for ch in (segmento or "") if ch.isdigit())
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        bcr.serie_set(conn, eid, servicio, anio_tarifario, _fnum(q_m3), _fnum(cmi_cobrado),
                      int(seg) if seg else None)
    db.audit(scope_of(user), "bcr_serie", "empresa", eid, f"{servicio} año {anio_tarifario}")
    return RedirectResponse(_dest(next, dflt, "msg=Serie+688+guardada"), status_code=303)


@app.post("/empresa/{eid}/bcr-poir-mods")
def bcr_poir_mods(request: Request, eid: int, servicio: str = Form(...), fechas: str = Form(""),
                  next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    crudas = fechas.replace(";", " ").replace(",", " ").replace("\n", " ").split()
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        p = bcr.param_get(conn, eid, servicio)
        fi = p["fecha_inicio_688"] if p else None
        n = poir.mods_set(conn, eid, servicio, crudas, fi)
    db.audit(scope_of(user), "poir_mods", "empresa", eid, f"{servicio}: {n} modificaciones")
    return RedirectResponse(_dest(next, dflt, f"msg={n}+modificaciones+del+POIR+registradas"), status_code=303)


@app.post("/empresa/{eid}/bcr-poir-cmi")
def bcr_poir_cmi(request: Request, eid: int, servicio: str = Form(...),
                 modificacion: int = Form(...), archivo: UploadFile = File(...),
                 next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    nombre = (archivo.filename or "").lower()
    if not nombre.endswith((".xlsx", ".xlsm")):
        return RedirectResponse(_dest(next, dflt, "err=Suba+un+archivo+Excel+(.xlsx)"), status_code=303)
    raw = archivo.file.read()
    filas, err = poir.leer_excel_cmi(raw)
    if err and not filas:
        return RedirectResponse(_dest(next, dflt, "err=" + ("; ".join(err)).replace(" ", "+")), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        n_act, n_cmi = poir.ingesta_modificacion(conn, eid, servicio, modificacion, filas, user["user_id"])
    db.audit(scope_of(user), "poir_cmi", "empresa", eid,
             f"{servicio} mod {modificacion}: {n_act} activos nuevos, {n_cmi} CMI")
    return RedirectResponse(_dest(next, dflt,
        f"msg=Mod+{modificacion}:+{n_cmi}+CMI+cargados+({n_act}+activos+nuevos)"), status_code=303)


@app.get("/empresa/{eid}/bcr-poir-plantilla")
def bcr_poir_plantilla(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    data = poir.plantilla_bytes()
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="plantilla_cmi_poir.xlsx"'})


@app.get("/empresa/{eid}/bcr-activos-plantilla")
def bcr_activos_plantilla(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    return Response(content=bcr.plantilla_activos_bytes(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="plantilla_activos_bcr0.xlsx"'})


@app.post("/empresa/{eid}/bcr-activos-csv")
async def bcr_activos_csv(request: Request, eid: int):
    """Carga masiva de los activos de la BCR₀ de inicio (CSV o Excel; varios archivos)."""
    if (r := _need_login(request)):
        return r
    form = await request.form()
    if (bad := _bad_csrf(request, form.get("csrf"))):
        return bad
    user = session_user(request)
    nxt = form.get("next") or f"/empresa/{eid}/inversiones?sec=bcr"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(nxt, nxt, "err=No+autorizado"), status_code=303)
    archivos = form.getlist("archivos")
    tot_ok, errs, n = 0, [], 0
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        for arch in archivos:
            if not getattr(arch, "filename", ""):
                continue
            raw = await arch.read()
            filas, e = bcr.leer_archivo_activos(raw, arch.filename)
            if e:
                errs.append(f"{arch.filename}: {e}"); continue
            ok, err = bcr.ingesta_activos(conn, eid, filas, user["user_id"])
            tot_ok += ok; errs += err; n += 1
    db.audit(scope_of(user), "bcr_activos_csv", "empresa", eid, f"{n} archivos, {tot_ok} activos")
    aviso = f"msg=BCR0:+{tot_ok}+activos+cargados+de+{n}+archivo(s)"
    if errs:
        aviso += ";+" + ",+".join(errs[:3]).replace(" ", "+") + ("+…" if len(errs) > 3 else "")
    return RedirectResponse(_dest(nxt, nxt, aviso), status_code=303)


def _ym(s):
    """Parsea 'YYYY-MM' (del <input type=month>) a (anio, mes); None si no aplica."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        a, m = s.split("-")[:2]
        a, m = int(a), int(m)
        if 1 <= m <= 12:
            return (a, m)
    except Exception:
        pass
    return None


@app.get("/ipc", response_class=HTMLResponse)
def ipc_form(request: Request, indice: str = "indice", desde: str = "", hasta: str = ""):
    if (r := _need_login(request)):
        return r
    if not rbac.can(session_user(request), "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    col = indice if indice in ix.MENSUALES else "indice"
    d, h = _ym(desde), _ym(hasta)
    with db.scope_conn(scope_of(session_user(request))) as conn:
        resumen = ix.resumen(conn)
        salario = ix.salario_serie(conn)
        graf = ix.datos_grafica(conn, col, d, h)
        prox_a, prox_m = ix.proximo_mes(conn)
        prox_sal = ix.proximo_anio_salario(conn)
    svg = ix.svg_grafica(graf)
    des_def = f'{graf["desde"][0]:04d}-{graf["desde"][1]:02d}' if graf["desde"] else ""
    has_def = f'{graf["hasta"][0]:04d}-{graf["hasta"][1]:02d}' if graf["hasta"] else ""
    return tpl.TemplateResponse(request, "ipc.html", _ctx(
        request, resumen=resumen, salario=salario, graf=graf, svg=svg, meses=ops.MESES,
        col=col, mensuales=ix.MENSUALES, orden=ix.ORDEN_MENSUAL,
        des_def=des_def, has_def=has_def, prox_anio=prox_a, prox_mes=prox_m, prox_sal=prox_sal))


@app.post("/ipc")
def ipc_post(request: Request, anio: int = Form(...), mes: int = Form(...),
             indice: str = Form(""), ipcs: str = Form(""), ictc: str = Form(""),
             fuente: str = Form("DANE"), csrf: str = Form("")):
    """Ingreso/actualización del dato mensual: IPC (obligatorio), IPC-SAR e ICTC (opcionales)."""
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    v_ipc = _fnum(indice)
    if v_ipc is None:
        return RedirectResponse("/ipc?err=El+IPC+es+obligatorio", status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO indice_ipc(anio,mes,indice,ipcs,ictc,fuente,procedencia,cargado_por) "
                "VALUES (:a,:m,:ipc,:ipcs,:ictc,:f,'reportada',:u) "
                "ON CONFLICT (anio,mes) DO UPDATE SET indice=excluded.indice, "
                " ipcs=COALESCE(excluded.ipcs, indice_ipc.ipcs), "
                " ictc=COALESCE(excluded.ictc, indice_ipc.ictc), "
                " fuente=excluded.fuente, procedencia=excluded.procedencia, cargado_por=excluded.cargado_por"),
                {"a": anio, "m": mes, "ipc": v_ipc, "ipcs": _fnum(ipcs), "ictc": _fnum(ictc),
                 "f": fuente.strip() or "DANE", "u": user["user_id"]})
    except Exception as e:
        return RedirectResponse(f"/ipc?err=No+se+pudo+guardar+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "cargar_indice_mensual", "ipc", None,
             f"{ops.MESES.get(mes, mes)}-{anio}: IPC={indice} IPC-SAR={ipcs or '—'} ICTC={ictc or '—'}")
    return RedirectResponse("/ipc?msg=Índice+mensual+guardado+(recuerde+reprocesar+la+indexación)",
                            status_code=303)


@app.post("/ipc/salario")
def ipc_salario(request: Request, anio: int = Form(...), valor: str = Form(""),
                fuente: str = Form(""), csrf: str = Form("")):
    """Salario mínimo (SMMLV): un valor por año."""
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    digitos = re.sub(r"[^\d]", "", valor or "")
    if not digitos:
        return RedirectResponse("/ipc?err=Valor+de+salario+inválido", status_code=303)
    v = float(digitos)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO salario_minimo(anio,valor,fuente,procedencia,cargado_por) "
                "VALUES (:a,:v,:f,'normativa',:u) "
                "ON CONFLICT (anio) DO UPDATE SET valor=excluded.valor, fuente=excluded.fuente, "
                " procedencia=excluded.procedencia, cargado_por=excluded.cargado_por"),
                {"a": anio, "v": v, "f": fuente.strip() or None, "u": user["user_id"]})
    except Exception as e:
        return RedirectResponse(f"/ipc?err=No+se+pudo+guardar+el+salario+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "cargar_smmlv", "ipc", None, f"{anio}={int(v)}")
    return RedirectResponse("/ipc?msg=Salario+mínimo+guardado", status_code=303)


# ------------------------------------------------------------------ permisos / auditoría
@app.get("/permisos", response_class=HTMLResponse)
def permisos(request: Request):
    if (r := _need_login(request)):
        return r
    return tpl.TemplateResponse(request, "permisos.html", _ctx(request, matriz=rbac.matriz()))


@app.get("/periodos", response_class=HTMLResponse)
def periodos_ref(request: Request):
    if (r := _need_login(request)):
        return r
    return tpl.TemplateResponse(request, "periodos.html", _ctx(request, periodos=per.PERIODOS))


@app.get("/auditoria", response_class=HTMLResponse)
def auditoria(request: Request):
    if (r := _need_login(request)):
        return r
    if not rbac.can(session_user(request), "ver_auditoria"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(session_user(request))) as conn:
        filas = conn.execute(text(
            "SELECT en,email,accion,objeto,empresa_id,detalle FROM auditoria "
            "ORDER BY en DESC LIMIT 100")).mappings().all()
    return tpl.TemplateResponse(request, "auditoria.html", _ctx(request, filas=filas))


# ------------------------------------------------------------------ API JSON (para pruebas de aislamiento)
@app.get("/api/empresas")
def api_empresas(request: Request):
    user = session_user(request)
    if not user:
        return JSONResponse({"error": "no autenticado"}, status_code=401)
    with db.scope_conn(scope_of(user)) as conn:
        rows = conn.execute(text("SELECT id,codigo,nombre FROM empresa ORDER BY id")).mappings().all()
    return {"usuario": user["email"], "rol": user["rol"], "empresas": [dict(r) for r in rows]}


@app.get("/api/empresa/{eid}/costos")
def api_costos(request: Request, eid: int):
    user = session_user(request)
    if not user:
        return JSONResponse({"error": "no autenticado"}, status_code=401)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT codigo,nombre FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return JSONResponse({"error": "empresa no disponible para este usuario"}, status_code=404)
        rows = conn.execute(text(
            "SELECT servicio,componente,valor,unidad FROM resultado_componente WHERE empresa_id=:e "
            "ORDER BY servicio,componente"), {"e": eid}).mappings().all()
    return {"empresa": dict(emp), "costos": [dict(r) for r in rows]}


@app.get("/salud")
def salud():
    return {"ok": True}
