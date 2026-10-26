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
import json
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
        cargado = conn.execute(text(
            "SELECT anio, servicio, count(DISTINCT mes) AS meses, "
            "round(avg(suscriptores))::int AS susc_prom, sum(m3_facturados) AS m3_total "
            "FROM carga_mensual WHERE empresa_id=:e GROUP BY anio, servicio "
            "ORDER BY anio DESC, servicio"), {"e": eid}).mappings().all()
    por_servicio = {}
    for row in res:
        por_servicio.setdefault(row["servicio"], []).append(row)
    return tpl.TemplateResponse(request, "empresa.html", _ctx(
        request, emp=emp, por_servicio=por_servicio, cargado=cargado, meses=ops.MESES,
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
        emp = conn.execute(text("SELECT id, codigo, fecha_inicio_1032 FROM empresa WHERE id=:e"),
                           {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        if not nucleo_service.perfil_existe(emp["codigo"]):
            return RedirectResponse(f"/empresa/{eid}?err=Sin+perfil+de+cálculo", status_code=303)
        # Año tarifario al que corresponde este recálculo (para la foto por año a diciembre).
        try:
            anio_snap = int(str(emp["fecha_inicio_1032"])[:4])
        except (TypeError, ValueError):
            anio_snap = 2026
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
            # Foto del componente para el año tarifario (histórico por año).
            conn.execute(text(
                "INSERT INTO resultado_componente_anio "
                "(empresa_id,anio,servicio,componente,valor,unidad,procedencia,fuente,articulo) "
                "VALUES (:e,:y,:s,:c,:v,:u,:p,:f,:a) "
                "ON CONFLICT (empresa_id,anio,servicio,componente) DO UPDATE SET "
                " valor=excluded.valor, unidad=excluded.unidad, procedencia=excluded.procedencia, "
                " fuente=excluded.fuente, articulo=excluded.articulo, snapshot_en=now()"),
                {"e": eid, "y": anio_snap, "s": f["servicio"], "c": f["componente"], "v": f["valor"],
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
                       aps_items: list[str] = Form([], alias="aps"), csrf: str = Form(""),
                       catalogo: UploadFile | None = File(None)):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "crear_empresa"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)

    # Catálogo de cuentas opcional al crear. Si no se sube uno válido, la empresa usa el
    # catálogo consolidado por defecto (y se puede subir/editar luego en la pestaña Balance).
    cat_texto, cat_n, cat_nom = None, 0, ""
    if catalogo is not None and (getattr(catalogo, "filename", "") or "").strip():
        try:
            _raw = catalogo.file.read()
            if _raw:
                _txt = _catalogo_texto_desde_archivo(_raw, catalogo.filename)
                _n = sum(1 for v in clf.cargar_catalogo(_txt).values() if v[1])
                if _n >= 5:
                    cat_texto, cat_n, cat_nom = _txt, _n, (catalogo.filename or "catalogo")[:200]
        except Exception:
            cat_texto = None

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
            if cat_texto:
                conn.execute(text(
                    "INSERT INTO catalogo_empresa(empresa_id,csv_texto,n_cuentas,nombre_archivo,cargado_por) "
                    "VALUES (:e,:t,:n,:f,:u) ON CONFLICT (empresa_id) DO UPDATE SET "
                    "csv_texto=excluded.csv_texto, n_cuentas=excluded.n_cuentas, "
                    "nombre_archivo=excluded.nombre_archivo, cargado_por=excluded.cargado_por, cargado_en=now()"),
                    {"e": eid, "t": cat_texto, "n": cat_n, "f": cat_nom, "u": user.get("user_id")})
    except Exception as e:
        return RedirectResponse(f"/empresa-nueva?err=No+se+pudo+crear+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "crear_empresa", "empresa", None, codigo)
    cat_msg = f"+·+catálogo+propio+({cat_n}+cuentas)" if cat_texto else "+·+catálogo+por+defecto"
    return RedirectResponse("/panel?msg=Empresa+creada:+" + codigo + cat_msg, status_code=303)


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
def procesar(request: Request, eid: int, csrf: str = Form(""), next: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/mensual"
    if not rbac.can(user, "procesar_indexacion"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        filas, ix = ops.procesar_empresa(conn, eid)
        fac = ops.derivar_factura(conn, eid)
        # Borradores de aprobación por cada evento de indexación (índice + fecha usados).
        # El usuario luego adjunta el acto administrativo; el monitoreo del 3 % se ancla en esta fecha.
        eventos = {}      # (anio, mes) -> {ipcs, ipc}
        for rows in ops.tablero(conn, eid).values():
            for x in rows:
                if x.get("indexado") or x.get("indexado_ipc"):
                    eventos[(x["anio"], x["mes"])] = {"ipcs": x.get("ipcs"), "ipc": x.get("ipc")}
        gen = 0
        for (anio, mes), idx in sorted(eventos.items()):
            fecha = f"{anio}-{int(mes):02d}-01"
            if conn.execute(text("SELECT 1 FROM aprobacion_costos WHERE empresa_id=:e AND fecha_indice=:f"),
                            {"e": eid, "f": fecha}).first():
                continue
            def _f(v):
                return f"{float(v):.2f}" if v is not None else "—"
            mnom = ops.MESES.get(mes, mes)
            ir = f"IPCs {_f(idx['ipcs'])} · IPC {_f(idx['ipc'])} ({mnom}-{anio})"
            conn.execute(text(
                "INSERT INTO aprobacion_costos(empresa_id,anio_tarifario,fecha_indice,indice_referencia,"
                "origen,observacion,creado_por) VALUES (:e,:y,:f,:ir,'automatica',:o,:u)"),
                {"e": eid, "y": anio, "f": fecha, "ir": ir,
                 "o": f"Borrador generado al procesar la actualización de {mnom}-{anio}. Adjuntar el acto administrativo.",
                 "u": user.get("user_id")})
            gen += 1
    db.audit(scope_of(user), "procesar_indexacion", "empresa", eid,
             f"{filas} meses, {ix} indexaciones, {fac} factura, {gen} borradores aprobación")
    extra = f";+{gen}+borrador(es)+de+aprobación+generados" if gen else ""
    return RedirectResponse(
        _dest(next, dflt, f"msg=Indexación+procesada+({filas}+meses,+{ix}+indexaciones);+factura:+{fac}+filas{extra}"),
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
    n_ok, clases, errores, meses_ok = 0, 0, [], []
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        # Meses que YA estaban cargados para este año y servicio (para avisar sobreescritura).
        _sv = {"AC": "acueducto", "AL": "alcantarillado", "ACUEDUCTO": "acueducto",
               "ALCANTARILLADO": "alcantarillado"}.get((servicio or "").strip().upper(), servicio)
        ya_cargados = {m for (m,) in conn.execute(text(
            "SELECT DISTINCT mes FROM carga_mensual_detalle "
            "WHERE empresa_id=:e AND anio=:a AND servicio=:s"),
            {"e": eid, "a": anio, "s": _sv}).all()}
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
                n_ok += 1; clases += ok; meses_ok.append(mes)
            else:
                errores.append(f"{ops.MESES.get(mes,mes)}:+" + (err[0] if err else "sin+datos"))
        if n_ok:
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargar_sui_lote", "empresa", eid,
             f"{servicio} {anio}: {n_ok} meses, {clases} clases, {len(errores)} errores")
    lista = "+(" + ",+".join(ops.MESES.get(m, str(m)) for m in sorted(set(meses_ok))) + ")" if meses_ok else ""
    aviso = f"msg=SUI+{servicio}+{anio}:+{n_ok}+mes(es)+cargados{lista}+·+{clases}+clases"
    rec = sorted(set(meses_ok) & ya_cargados)
    if rec:
        aviso += (";+⚠+ya+estaban+cargados+y+se+ACTUALIZARON:+"
                  + ",+".join(ops.MESES.get(m, str(m)) for m in rec))
    if errores:
        aviso += ";+fallaron:+" + ",+".join(errores[:4]).replace(" ", "+")
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


@app.post("/empresa/{eid}/cargue-eliminar")
def cargue_eliminar(request: Request, eid: int, concepto: str = Form(...), anio: int = Form(...),
                    mes: int = Form(...), servicio: str = Form(...), next: str = Form(""), csrf: str = Form("")):
    """Elimina un cargue (un mes-servicio de un concepto). Comercial borra el detalle por clase y el
    agregado y re-deriva la factura; balance borra los numeradores; agua, la macromedición."""
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    fuente = concepto if concepto in ("comercial", "balance", "agua") else "comercial"
    dflt = f"/empresa/{eid}/cargar?fuente={fuente}"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    tablas = {"comercial": ["carga_mensual_detalle", "carga_mensual"],
              "balance": ["numerador_mensual"], "agua": ["macromedicion"]}
    if concepto not in tablas:
        return RedirectResponse(_dest(next, dflt, "err=Concepto+inválido"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        if not conn.execute(text("SELECT 1 FROM empresa WHERE id=:e"), {"e": eid}).first():
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        n = 0
        for t in tablas[concepto]:
            res = conn.execute(text(
                f"DELETE FROM {t} WHERE empresa_id=:e AND anio=:a AND mes=:m AND servicio=:s"),
                {"e": eid, "a": anio, "m": mes, "s": servicio})
            n += res.rowcount or 0
        if concepto == "comercial":
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargue_eliminar", "empresa", eid,
             f"{concepto} {servicio} {ops.MESES.get(mes, mes)}-{anio}: {n} filas")
    aviso = f"msg=Eliminado:+{concepto}+{servicio}+{ops.MESES.get(mes, mes)}-{anio}+({n}+filas)"
    return RedirectResponse(_dest(next, dflt, aviso), status_code=303)


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
    base = _os.path.join(config.BASE_DIR, "catalogos")
    p = _os.path.join(base, f"catalogo_clasificacion_{codigo.lower().replace('_','')}.csv")
    if _os.path.exists(p):
        return p
    # Respaldo: catálogo de clasificación por defecto (PUC estándar de acueducto/alcantarillado)
    # cuando la empresa aún no tiene el suyo; las cuentas no mapeadas quedan como «sin clasificar».
    d = _os.path.join(base, "catalogo_clasificacion_default.csv")
    return d if _os.path.exists(d) else None


def _catalogo_texto_desde_archivo(raw, nombre):
    """Bytes de un catálogo (CSV o Excel) -> texto CSV. Convierte .xlsx/.xlsm con openpyxl y
    decodifica el CSV probando varias codificaciones. Lanza excepción solo si no se puede leer."""
    if (nombre or "").lower().endswith((".xlsx", ".xlsm")):
        import openpyxl, tempfile, csv as _csv, io as _io, os as _os
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            tf.write(raw); tmp = tf.name
        try:
            wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
            buf = _io.StringIO(); w = _csv.writer(buf)
            for row in wb.worksheets[0].iter_rows(values_only=True):
                w.writerow(["" if c is None else c for c in row])
            wb.close()
        finally:
            _os.unlink(tmp)
        return buf.getvalue()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", "replace")


def _catalogo_default_texto():
    import os as _os
    p = _os.path.join(config.BASE_DIR, "catalogos", "catalogo_clasificacion_default.csv")
    return open(p, encoding="utf-8").read() if _os.path.exists(p) else None


def _catalogo_para(conn, eid, codigo):
    """Catálogo de clasificación a usar: el que subió la empresa (BD) y, si no hay, el de archivo
    (el específico de la empresa o el por defecto de Las Ceibas). Devuelve el dict de clf o None."""
    row = conn.execute(text("SELECT csv_texto FROM catalogo_empresa WHERE empresa_id=:e"), {"e": eid}).first()
    if row and row[0]:
        return clf.cargar_catalogo(row[0])
    p = _catalogo_path(codigo)
    return clf.cargar_catalogo(open(p, encoding="utf-8").read()) if p else None


@app.get("/empresa/{eid}/catalogo-plantilla")
def catalogo_plantilla(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    txt = _catalogo_default_texto() or "codigo,codigo_norm,nombre,clase,subcomponente,componente,traslado\n"
    return Response(txt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=plantilla_catalogo_cuentas.csv"})


# Plantillas CSV de cargue (encabezado + filas de ejemplo). El cargue acepta coma o ';',
# mayúsculas en los encabezados y meses por número o nombre ('Enero').
PLANTILLAS = {
    "macromedicion": ("plantilla_agua_producida.csv",
        "anio,mes,servicio,punto,m3_producido,m3_bloque_entregado,m3_bloque_recibido",
        ["2026,7,acueducto,P1,4285559,,", "2026,8,acueducto,P1,4227059,,"]),
    "comercial": ("plantilla_comercial.csv",
        "anio,mes,servicio,clase,suscriptores,m3,m3_subsidiable",
        ["2026,7,acueducto,1,1200,19200,19200", "2026,7,acueducto,5,900,21600,0"]),
    "factores": ("plantilla_factores_subsidio.csv",
        "vigencia,servicio,clase,factor_cargofijo,factor_consumo",
        ["2026-07,acueducto,1,-0.70,-0.70", "2026-07,acueducto,5,0.50,0.50"]),
    "indicadores": ("plantilla_indicadores.csv",
        "anio,mes,servicio,ipuf_real,continuidad_h,irca,reclamaciones,cortes,reconexiones",
        ["2026,7,acueducto,6.0,24,0,,,"]),
    "indices": ("plantilla_ipc.csv",
        "anio,mes,ipc,ipcs",
        ["2026,7,112.34,110.20"]),
    "bcr_serie": ("plantilla_agua_facturada_688.csv",
        "servicio,anio,mes,agua_facturada_m3,cmi_cobrado,segmento688",
        ["acueducto,1,1,2040000,980.50,2", "acueducto,1,2,1980000,980.50,2",
         "acueducto,1,3,2010000,1010.30,2", "alcantarillado,1,1,1840000,640.00,2"]),
    "balance": ("plantilla_balance_prueba.csv",
        "cuenta,nombre,saldo",
        ["511095,Gastos de personal administrativo,125000000",
         "750505,Energía eléctrica,84000000",
         "755005,Productos químicos,33000000"]),
}


@app.get("/empresa/{eid}/plantilla/{tipo}")
def plantilla_csv(request: Request, eid: int, tipo: str):
    if (r := _need_login(request)):
        return r
    p = PLANTILLAS.get(tipo)
    if not p:
        return RedirectResponse(f"/empresa/{eid}/cargar?err=Plantilla+no+disponible", status_code=303)
    nombre, header, ejemplos = p
    txt = header + "\n" + "\n".join(ejemplos) + "\n"
    return Response(txt, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})


@app.post("/empresa/{eid}/catalogo-cuentas")
def catalogo_subir(request: Request, eid: int, archivo: UploadFile = File(...),
                   next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=balance"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    raw = archivo.file.read()
    nom = archivo.filename or "catalogo.csv"
    try:
        texto = _catalogo_texto_desde_archivo(raw, nom)
    except Exception as e:
        return RedirectResponse(_dest(next, dflt, f"err=No+se+pudo+leer+el+catálogo+({type(e).__name__})"), status_code=303)
    cat = clf.cargar_catalogo(texto)
    n = sum(1 for v in cat.values() if v[1])      # cuentas con componente
    if n < 5:
        return RedirectResponse(_dest(next, dflt,
            "err=El+archivo+no+parece+un+catálogo+de+cuentas+(revisa+las+columnas+codigo/componente;+usa+la+plantilla)"),
            status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        if not conn.execute(text("SELECT 1 FROM empresa WHERE id=:e"), {"e": eid}).first():
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        conn.execute(text(
            "INSERT INTO catalogo_empresa(empresa_id,csv_texto,n_cuentas,nombre_archivo,cargado_por) "
            "VALUES (:e,:t,:n,:f,:u) ON CONFLICT (empresa_id) DO UPDATE SET "
            "csv_texto=excluded.csv_texto, n_cuentas=excluded.n_cuentas, "
            "nombre_archivo=excluded.nombre_archivo, cargado_por=excluded.cargado_por, cargado_en=now()"),
            {"e": eid, "t": texto, "n": n, "f": nom[:200], "u": user.get("id")})
    db.audit(scope_of(user), "catalogo_subir", "empresa", eid, f"{nom}: {n} cuentas")
    return RedirectResponse(_dest(next, dflt, f"msg=Catálogo+cargado+({n}+cuentas)"), status_code=303)


@app.post("/empresa/{eid}/catalogo-cuentas/reset")
def catalogo_reset(request: Request, eid: int, next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/cargar?fuente=balance"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        conn.execute(text("DELETE FROM catalogo_empresa WHERE empresa_id=:e"), {"e": eid})
    db.audit(scope_of(user), "catalogo_reset", "empresa", eid, "vuelve al catálogo por defecto")
    return RedirectResponse(_dest(next, dflt, "msg=Catálogo+restablecido+al+de+Las+Ceibas+(por+defecto)"), status_code=303)


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
        catalogo = _catalogo_para(conn, eid, emp["codigo"])
        if not catalogo:
            return RedirectResponse(
                _dest(next, dflt, "err=Falta+el+catálogo+de+clasificación+de+esta+empresa"),
                status_code=303)
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
        request, emp=emp, serie=serie, resumen=resumen, gatillo=ops.GATILLO, meses=ops.MESES,
        puede_procesar=rbac.can(user, "procesar_indexacion")))


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

        def _celdas(sql):
            # {anio: {servicio: set(meses cargados)}}
            d = {}
            for a, m, s in conn.execute(text(sql), {"e": eid}).all():
                d.setdefault(a, {}).setdefault(s, set()).add(m)
            return d
        com_m = _celdas("SELECT DISTINCT anio, mes, servicio FROM carga_mensual WHERE empresa_id=:e")
        bal_m = _celdas("SELECT DISTINCT anio, mes, servicio FROM numerador_mensual WHERE empresa_id=:e")
        agua_m = _celdas("SELECT DISTINCT anio, mes, servicio FROM macromedicion WHERE empresa_id=:e")
        fsub = dict(conn.execute(text(
            "SELECT vigencia, count(*) FROM factor_subsidio WHERE empresa_id=:e GROUP BY vigencia"),
            {"e": eid}).all())
    servicios = [s for s, on in (("acueducto", emp["presta_ac"]), ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
    # El agua producida (macromedición) solo aplica a acueducto; el alcantarillado no la carga.
    serv_agua = [s for s in servicios if s == "acueducto"]
    # El período de inicio se calcula con la línea base 2024–2025 (dos años completos).
    anios = per.PERIODOS[0]["anios_base"]              # [2024, 2025]
    matriz = [
        {"clave": "comercial", "nombre": "Comercial (suscriptores y consumos)", "cel": com_m, "serv": servicios},
        {"clave": "balance", "nombre": "Balance de prueba (numeradores CMO/CMI/CMICT)", "cel": bal_m, "serv": servicios},
        {"clave": "agua", "nombre": "Agua producida / macromedición (solo acueducto)", "cel": agua_m, "serv": serv_agua},
    ]
    resumen = [
        {"nombre": "Configuración del APS", "valor": f"{apsres['n_completos']}/{apsres['n_municipios']} completos",
         "ok": apsres["n_municipios"] > 0 and apsres["n_completos"] == apsres["n_municipios"]},
        {"nombre": "Factores de subsidio y contribución", "datos": fsub},
        {"nombre": "Costos particulares (art. Res. 1032)", "pendiente": True},
    ]
    return tpl.TemplateResponse(request, "validacion.html", _ctx(
        request, emp=emp, matriz=matriz, resumen=resumen, servicios=servicios,
        anios=anios, meses_num=list(range(1, 13)), meses=ops.MESES))


# ------------------------------------------------------------------ Resultados · Costos de referencia por año tarifario
@app.get("/empresa/{eid}/resultados", response_class=HTMLResponse)
def resultados_anio(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        servicios = [s for s, on in (("acueducto", emp["presta_ac"]), ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
        try:
            anio_inicio = int(str(emp["fecha_inicio_1032"])[:4])
        except (TypeError, ValueError):
            anio_inicio = 2026
        snaps = {}        # {anio: {servicio: {componente: {...}}}}
        for a, s, c, v, u, pr, ar in conn.execute(text(
                "SELECT anio, servicio, componente, valor, unidad, procedencia, articulo "
                "FROM resultado_componente_anio WHERE empresa_id=:e"), {"e": eid}).all():
            snaps.setdefault(a, {}).setdefault(s, {})[c] = {"valor": v, "unidad": u, "procedencia": pr, "articulo": ar}
        cur = {}          # componentes actuales (respaldo para el año de inicio sin foto)
        for s, c, v, u, pr, ar in conn.execute(text(
                "SELECT servicio, componente, valor, unidad, procedencia, articulo "
                "FROM resultado_componente WHERE empresa_id=:e"), {"e": eid}).all():
            cur.setdefault(s, {})[c] = {"valor": v, "unidad": u, "procedencia": pr, "articulo": ar}
        precio = {}       # {anio: {servicio: {cf, cc, mes, fa}}} — tarifa al último mes (actualización vigente)
        for s, a, m, cf, cc, fa in conn.execute(text(
                "SELECT DISTINCT ON (servicio, anio) servicio, anio, mes, cargo_fijo, cargo_consumo, factor_acumulado "
                "FROM tarifa_vigente WHERE empresa_id=:e ORDER BY servicio, anio, mes DESC"), {"e": eid}).all():
            precio.setdefault(a, {})[s] = {"cf": cf, "cc": cc, "mes": m, "fa": fa}
    if anio_inicio not in snaps and cur:
        snaps[anio_inicio] = cur
    anios = sorted(set([anio_inicio]) | set(snaps) | set(precio))
    orden = ["CMA", "CMO", "CMI", "CMICT"]
    datos = []
    for a in anios:
        comps = snaps.get(a, {})
        todos = set()
        for s in servicios:
            todos |= set(comps.get(s, {}).keys())
        todos.discard("CARGO_FIJO"); todos.discard("CARGO_CONSUMO")
        comp_orden = [c for c in orden if c in todos] + sorted(c for c in todos if c not in orden)
        meta = {}      # unidad/artículo por componente (de cualquier servicio que lo tenga)
        for s in servicios:
            for c, cell in comps.get(s, {}).items():
                if c not in meta:
                    meta[c] = {"unidad": cell.get("unidad"), "articulo": cell.get("articulo")}
        # Precio por servicio: base a dic I-1 (foto CARGO_*) vs. última actualización (tarifa_vigente).
        precio_serv = {}
        for s in servicios:
            base = comps.get(s, {})
            act = precio.get(a, {}).get(s, {})
            precio_serv[s] = {
                "cf_base": (base.get("CARGO_FIJO") or {}).get("valor"),
                "cc_base": (base.get("CARGO_CONSUMO") or {}).get("valor"),
                "cf_act": act.get("cf"), "cc_act": act.get("cc"),
                "mes": act.get("mes"), "fa": act.get("fa")}
        datos.append({"anio": a, "label": ANIOS_TAR.get(a, f"Año tarifario {a}"), "anio_prev": a - 1,
                      "componentes": comp_orden, "meta": meta,
                      "valores": {s: comps.get(s, {}) for s in servicios},
                      "precio_serv": precio_serv})
    return tpl.TemplateResponse(request, "resultados.html", _ctx(
        request, emp=emp, servicios=servicios, datos=datos, meses=ops.MESES))


# ------------------------------------------------------------------ Aprobaciones de costos de referencia
@app.get("/empresa/{eid}/aprobaciones", response_class=HTMLResponse)
def aprobaciones(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        actos = [dict(r) for r in conn.execute(text(
            "SELECT id, anio_tarifario, acto_administrativo, fecha_aprobacion, indice_referencia, "
            "fecha_indice, origen, observacion, creado_en "
            "FROM aprobacion_costos WHERE empresa_id=:e ORDER BY anio_tarifario DESC, fecha_indice DESC NULLS LAST, creado_en DESC"),
            {"e": eid}).mappings().all()]
        archivos = {}
        for f in conn.execute(text(
                "SELECT id, aprobacion_id, nombre, tipo, tamano, subido_en FROM aprobacion_archivo "
                "WHERE empresa_id=:e ORDER BY subido_en"), {"e": eid}).mappings().all():
            archivos.setdefault(f["aprobacion_id"], []).append(dict(f))
    return tpl.TemplateResponse(request, "aprobaciones.html", _ctx(
        request, emp=emp, actos=actos, archivos=archivos, anios_tar=ANIOS_TAR,
        puede=rbac.can(user, "cargar_mensual")))


@app.post("/empresa/{eid}/aprobaciones/nueva")
def aprobacion_nueva(request: Request, eid: int, anio_tarifario: int = Form(...),
                     acto_administrativo: str = Form(""), fecha_aprobacion: str = Form(""),
                     indice_referencia: str = Form(""), fecha_indice: str = Form(""),
                     observacion: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/aprobaciones"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            if not conn.execute(text("SELECT 1 FROM empresa WHERE id=:e"), {"e": eid}).first():
                return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
            conn.execute(text(
                "INSERT INTO aprobacion_costos(empresa_id,anio_tarifario,acto_administrativo,"
                "fecha_aprobacion,indice_referencia,fecha_indice,observacion,creado_por) "
                "VALUES (:e,:y,:a,:f,:ir,:fi,:o,:u)"),
                {"e": eid, "y": anio_tarifario, "a": acto_administrativo.strip() or None,
                 "f": (fecha_aprobacion.strip() or None), "ir": indice_referencia.strip() or None,
                 "fi": (fecha_indice.strip() or None), "o": observacion.strip() or None,
                 "u": user.get("user_id")})
    except Exception as e:
        return RedirectResponse(dflt + f"?err=No+se+pudo+registrar+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "aprobacion_nueva", "empresa", eid, f"{anio_tarifario}:{acto_administrativo}")
    return RedirectResponse(dflt + "?msg=Aprobación+registrada", status_code=303)


@app.post("/empresa/{eid}/aprobaciones/{apid}/editar")
def aprobacion_editar(request: Request, eid: int, apid: int, acto_administrativo: str = Form(""),
                      fecha_aprobacion: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/aprobaciones"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        conn.execute(text(
            "UPDATE aprobacion_costos SET acto_administrativo=:a, fecha_aprobacion=:f "
            "WHERE id=:i AND empresa_id=:e"),
            {"a": acto_administrativo.strip() or None, "f": (fecha_aprobacion.strip() or None),
             "i": apid, "e": eid})
    db.audit(scope_of(user), "aprobacion_editar", "empresa", eid, f"{apid}:{acto_administrativo}")
    return RedirectResponse(dflt + "?msg=Aprobación+actualizada", status_code=303)


@app.post("/empresa/{eid}/aprobaciones/{apid}/archivo")
def aprobacion_archivo_subir(request: Request, eid: int, apid: int,
                             archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/aprobaciones"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    raw = archivo.file.read()
    nombre = (archivo.filename or "soporte").strip()
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in aps.EXT_PERMITIDAS:
        return RedirectResponse(dflt + f"?err=Formato+no+admitido+({ext})", status_code=303)
    if len(raw) > aps.MAX_BYTES:
        return RedirectResponse(dflt + "?err=Archivo+supera+25+MB", status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            ok = conn.execute(text("SELECT 1 FROM aprobacion_costos WHERE id=:a AND empresa_id=:e"),
                              {"a": apid, "e": eid}).first()
            if not ok:
                return RedirectResponse(dflt + "?err=Aprobación+no+disponible", status_code=303)
            conn.execute(text(
                "INSERT INTO aprobacion_archivo(aprobacion_id,empresa_id,nombre,tipo,tamano,contenido,subido_por) "
                "VALUES (:a,:e,:n,:t,:z,:c,:u)"),
                {"a": apid, "e": eid, "n": nombre, "t": ext, "z": len(raw), "c": raw, "u": user.get("user_id")})
    except Exception as e:
        return RedirectResponse(dflt + f"?err=No+se+pudo+subir+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "aprobacion_archivo", "empresa", eid, f"{apid}:{nombre}")
    return RedirectResponse(dflt + "?msg=Soporte+cargado", status_code=303)


@app.get("/empresa/{eid}/aprobaciones/archivo/{fid}")
def aprobacion_archivo_bajar(request: Request, eid: int, fid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        f = conn.execute(text(
            "SELECT nombre, contenido FROM aprobacion_archivo WHERE id=:f AND empresa_id=:e"),
            {"f": fid, "e": eid}).mappings().first()
    if not f:
        return RedirectResponse(f"/empresa/{eid}/aprobaciones?err=Archivo+no+disponible", status_code=303)
    import mimetypes
    media = mimetypes.guess_type(f["nombre"] or "")[0] or "application/octet-stream"
    seguro = (f["nombre"] or "soporte").replace('"', "")
    return Response(content=bytes(f["contenido"]), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{seguro}"'})


@app.post("/empresa/{eid}/aprobaciones/{apid}/eliminar")
def aprobacion_eliminar(request: Request, eid: int, apid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/aprobaciones"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        conn.execute(text("DELETE FROM aprobacion_costos WHERE id=:a AND empresa_id=:e"),
                     {"a": apid, "e": eid})
    db.audit(scope_of(user), "aprobacion_eliminar", "empresa", eid, str(apid))
    return RedirectResponse(dflt + "?msg=Aprobación+eliminada", status_code=303)


@app.post("/empresa/{eid}/aprobaciones/archivo/{fid}/eliminar")
def aprobacion_archivo_eliminar(request: Request, eid: int, fid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/aprobaciones"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        conn.execute(text("DELETE FROM aprobacion_archivo WHERE id=:f AND empresa_id=:e"),
                     {"f": fid, "e": eid})
    db.audit(scope_of(user), "aprobacion_archivo_eliminar", "empresa", eid, str(fid))
    return RedirectResponse(dflt + "?msg=Soporte+eliminado", status_code=303)


# ------------------------------------------------------------------ Seguimiento a las metas (Res. CRA 1032, Cap. 2)
ESTADOS_META = {"pendiente": "Pendiente", "en_proceso": "En proceso",
                "cumplido": "Cumplido", "no_aplica": "No aplica"}


@app.get("/empresa/{eid}/metas", response_class=HTMLResponse)
def metas(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = _emp_or_redirect(conn, eid)
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        servicios_emp = [s for s, on in (("acueducto", emp["presta_ac"]),
                                         ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
        cat = conn.execute(text(
            "SELECT c.id, c.codigo, c.servicio, c.objetivo, c.factor, c.nombre, c.tipo, "
            "       c.valor_estandar, c.articulo, "
            "       me.linea_base, me.meta_valor, me.anio_meta, me.estado, me.observacion "
            "FROM meta_catalogo c "
            "LEFT JOIN meta_empresa me ON me.meta_id=c.id AND me.empresa_id=:e "
            "WHERE c.servicio = ANY(:ss) ORDER BY c.orden"),
            {"e": eid, "ss": servicios_emp}).mappings().all()
        arch = {}
        for a in conn.execute(text(
                "SELECT id, meta_id, nombre, tamano FROM meta_archivo WHERE empresa_id=:e ORDER BY subido_en"),
                {"e": eid}).mappings().all():
            arch.setdefault(a["meta_id"], []).append(dict(a))
    grupos = {}   # servicio -> objetivo -> [metas]
    n_est = n_bp = 0
    for m in cat:
        grupos.setdefault(m["servicio"], {}).setdefault(m["objetivo"], []).append(dict(m))
        if m["tipo"] == "estandar":
            n_est += 1
        else:
            n_bp += 1
    return tpl.TemplateResponse(request, "metas.html", _ctx(
        request, emp=emp, grupos=grupos, archivos=arch, estados=ESTADOS_META,
        n_est=n_est, n_bp=n_bp, puede=rbac.can(user, "cargar_mensual")))


@app.post("/empresa/{eid}/metas/{mid}/editar")
def meta_editar(request: Request, eid: int, mid: int, linea_base: str = Form(""),
                meta_valor: str = Form(""), anio_meta: str = Form(""),
                estado: str = Form("pendiente"), observacion: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/metas"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    est = estado if estado in ESTADOS_META else "pendiente"
    try:
        anio = int(anio_meta) if anio_meta.strip() else None
    except ValueError:
        anio = None
    try:
        with db.scope_conn(scope_of(user)) as conn:
            if not conn.execute(text("SELECT 1 FROM meta_catalogo WHERE id=:m"), {"m": mid}).first():
                return RedirectResponse(dflt + "?err=Meta+no+disponible", status_code=303)
            conn.execute(text(
                "INSERT INTO meta_empresa(empresa_id,meta_id,linea_base,meta_valor,anio_meta,estado,"
                "observacion,actualizado_por) VALUES (:e,:m,:lb,:mv,:a,:es,:o,:u) "
                "ON CONFLICT (empresa_id,meta_id) DO UPDATE SET linea_base=excluded.linea_base, "
                " meta_valor=excluded.meta_valor, anio_meta=excluded.anio_meta, estado=excluded.estado, "
                " observacion=excluded.observacion, actualizado_por=excluded.actualizado_por, actualizado_en=now()"),
                {"e": eid, "m": mid, "lb": linea_base.strip() or None, "mv": meta_valor.strip() or None,
                 "a": anio, "es": est, "o": observacion.strip() or None, "u": user.get("user_id")})
    except Exception as e:
        return RedirectResponse(dflt + f"?err=No+se+pudo+guardar+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "meta_editar", "empresa", eid, f"{mid}:{est}")
    return RedirectResponse(dflt + f"?msg=Meta+actualizada#m{mid}", status_code=303)


@app.post("/empresa/{eid}/metas/{mid}/archivo")
def meta_archivo_subir(request: Request, eid: int, mid: int,
                       archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/metas"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    raw = archivo.file.read()
    nombre = (archivo.filename or "soporte").strip()
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in aps.EXT_PERMITIDAS:
        return RedirectResponse(dflt + f"?err=Formato+no+admitido+({ext})", status_code=303)
    if len(raw) > aps.MAX_BYTES:
        return RedirectResponse(dflt + "?err=Archivo+supera+25+MB", status_code=303)
    try:
        with db.scope_conn(scope_of(user)) as conn:
            if not conn.execute(text("SELECT 1 FROM meta_catalogo WHERE id=:m"), {"m": mid}).first():
                return RedirectResponse(dflt + "?err=Meta+no+disponible", status_code=303)
            conn.execute(text(
                "INSERT INTO meta_archivo(empresa_id,meta_id,nombre,tipo,tamano,contenido,subido_por) "
                "VALUES (:e,:m,:n,:t,:z,:c,:u)"),
                {"e": eid, "m": mid, "n": nombre, "t": ext, "z": len(raw), "c": raw, "u": user.get("user_id")})
    except Exception as e:
        return RedirectResponse(dflt + f"?err=No+se+pudo+subir+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "meta_archivo", "empresa", eid, f"{mid}:{nombre}")
    return RedirectResponse(dflt + f"?msg=Soporte+cargado#m{mid}", status_code=303)


@app.get("/empresa/{eid}/metas/archivo/{fid}")
def meta_archivo_bajar(request: Request, eid: int, fid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        f = conn.execute(text(
            "SELECT nombre, contenido FROM meta_archivo WHERE id=:f AND empresa_id=:e"),
            {"f": fid, "e": eid}).mappings().first()
    if not f:
        return RedirectResponse(f"/empresa/{eid}/metas?err=Archivo+no+disponible", status_code=303)
    import mimetypes
    media = mimetypes.guess_type(f["nombre"] or "")[0] or "application/octet-stream"
    seguro = (f["nombre"] or "soporte").replace('"', "")
    return Response(content=bytes(f["contenido"]), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{seguro}"'})


@app.post("/empresa/{eid}/metas/archivo/{fid}/eliminar")
def meta_archivo_eliminar(request: Request, eid: int, fid: int, csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/metas"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(dflt + "?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        conn.execute(text("DELETE FROM meta_archivo WHERE id=:f AND empresa_id=:e"),
                     {"f": fid, "e": eid})
    db.audit(scope_of(user), "meta_archivo_eliminar", "empresa", eid, str(fid))
    return RedirectResponse(dflt + "?msg=Soporte+eliminado", status_code=303)


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
        # (1) Ingresos estimados: facturación teórica del último mes con tarifa, por servicio
        filas = conn.execute(text(
            "SELECT tv.servicio, tv.anio, tv.mes, tv.cargo_fijo, tv.cargo_consumo, "
            "       cm.suscriptores, cm.m3_facturados "
            "FROM tarifa_vigente tv "
            "LEFT JOIN carga_mensual cm ON cm.empresa_id=tv.empresa_id AND cm.anio=tv.anio "
            "     AND cm.mes=tv.mes AND cm.servicio=tv.servicio "
            "WHERE tv.empresa_id=:e AND (tv.anio,tv.mes) = ("
            "   SELECT anio,mes FROM tarifa_vigente WHERE empresa_id=:e ORDER BY anio DESC, mes DESC LIMIT 1) "
            "ORDER BY tv.servicio"), {"e": eid}).mappings().all()
        fact = {r["servicio"]: r for r in filas}
        # (2) CCP del período (m³) por servicio — último acumulado disponible
        ccp_rows = conn.execute(text(
            "SELECT DISTINCT ON (servicio) servicio, anio, mes, ccp_acum, ccp_mes "
            "FROM costo_referencia_mensual WHERE empresa_id=:e "
            "ORDER BY servicio, anio DESC, mes DESC"), {"e": eid}).mappings().all()
        ccp_por_serv = {r["servicio"]: r for r in ccp_rows}
        # (3) Energía (CE) y tasa retributiva (TA): numeradores base (dic-2025) por servicio
        comp_rows = conn.execute(text(
            "SELECT servicio, concepto, SUM(valor) AS v, MAX(anio) AS anio "
            "FROM numerador_mensual WHERE empresa_id=:e AND concepto IN ('CE','TA') "
            "GROUP BY servicio, concepto"), {"e": eid}).mappings().all()
        comp = {}
        for r in comp_rows:
            comp.setdefault(r["servicio"], {})[r["concepto"]] = r
        # (4) Insumos del simulador de oferta: numeradores del CMO, resultados base y drivers
        num_all = {}
        for r in conn.execute(text(
                "SELECT servicio, concepto, SUM(valor) AS v FROM numerador_mensual "
                "WHERE empresa_id=:e AND concepto IN ('COCe','CE','CIQ','COIR') GROUP BY servicio, concepto"),
                {"e": eid}).mappings().all():
            num_all.setdefault(r["servicio"], {})[r["concepto"]] = float(r["v"] or 0.0)
        rc_comp = {}
        for r in conn.execute(text(
                "SELECT servicio, componente, valor FROM resultado_componente WHERE empresa_id=:e "
                "AND componente IN ('CMA','CMO','CMI','CMICT','CARGO_FIJO','CARGO_CONSUMO')"),
                {"e": eid}).mappings().all():
            rc_comp.setdefault(r["servicio"], {})[r["componente"]] = (
                float(r["valor"]) if r["valor"] is not None else None)
        drv = {}
        for r in conn.execute(text(
                "SELECT servicio, AVG(n_mes) AS n, SUM(af_mes) AS af, SUM(ap_mes) AS ap, "
                "SUM(ccp_mes) AS ccp, COUNT(*) AS meses FROM costo_referencia_mensual "
                "WHERE empresa_id=:e GROUP BY servicio"), {"e": eid}).mappings().all():
            drv[r["servicio"]] = r
        ipuf_est = rc.ipuf_estrella(conn, eid)
        servicios_emp = [s for s, on in (("acueducto", emp["presta_ac"]),
                                         ("alcantarillado", emp["presta_al"])) if on] or ["acueducto"]
    serv = []
    tot_ing = 0.0

    def _num(x):
        return float(x) if x is not None else None

    for s in servicios_emp:
        r0 = fact.get(s)
        CF = _num(r0["cargo_fijo"]) if r0 else None
        CC = _num(r0["cargo_consumo"]) if r0 else None
        susc = (r0["suscriptores"] or 0) if r0 else 0
        m3 = _num(r0["m3_facturados"]) or 0.0 if r0 else 0.0
        ingreso = (CF or 0.0) * susc + (CC or 0.0) * m3 if r0 else None
        if ingreso and (susc or m3):
            tot_ing += ingreso
        cc_ccp = ccp_por_serv.get(s)
        ce = comp.get(s, {}).get("CE")
        ta = comp.get(s, {}).get("TA")
        serv.append({
            "servicio": s,
            "anio": r0["anio"] if r0 else None, "mes": r0["mes"] if r0 else None,
            "cf": CF, "cc": CC, "susc": susc, "m3": m3,
            "ingreso": ingreso, "tiene_cantidades": bool(susc or m3),
            "castigos": 0.0,                       # período de inicio: sin descuentos por calidad aún
            "ccp": _num(cc_ccp["ccp_acum"]) if cc_ccp else None,
            "ccp_ref": (f"{ops.MESES.get(cc_ccp['mes'], cc_ccp['mes'])}-{cc_ccp['anio']}" if cc_ccp else None),
            "energia": _num(ce["v"]) if ce else None,
            "energia_anio": ce["anio"] if ce else None,
            "tasa_retributiva": _num(ta["v"]) if ta else None,
            "ta_anio": ta["anio"] if ta else None,
        })
    # Simulador de oferta: baseline por servicio para recálculo en vivo (JS)
    sim = []
    for s in servicios_emp:
        rcx = rc_comp.get(s, {}); d = drv.get(s); nums = num_all.get(s, {})
        if not d or rcx.get("CMO") is None or rcx.get("CARGO_CONSUMO") is None:
            continue
        ap_v = float(d["ap"] or 0.0)
        coce = nums.get("COCe", 0.0); ce_v = nums.get("CE", 0.0)
        ciq = nums.get("CIQ", 0.0); coir = nums.get("COIR", 0.0)
        sim.append({
            "servicio": s, "es_ac": ap_v > 0,
            "n": float(d["n"] or 0.0), "af": float(d["af"] or 0.0), "ap": ap_v,
            "meses": int(d["meses"] or 0), "ipuf_est": float(ipuf_est or 0.0),
            "ccp_base": float(d["ccp"] or 0.0),
            "cma": rcx.get("CMA"), "cmo": rcx.get("CMO"), "cmi": rcx.get("CMI") or 0.0,
            "cmict": rcx.get("CMICT") or 0.0,
            "cargo_fijo": rcx.get("CARGO_FIJO") if rcx.get("CARGO_FIJO") is not None else rcx.get("CMA"),
            "cargo_consumo": rcx.get("CARGO_CONSUMO"),
            "coce": coce, "ce": ce_v, "ciq": ciq, "coir": coir, "s": coce + ce_v + ciq + coir,
        })
    return tpl.TemplateResponse(request, "suficiencia.html", _ctx(
        request, emp=emp, serv=serv, tot_ing=tot_ing, meses=ops.MESES,
        sim=sim, sim_json=json.dumps(sim)))


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
        cat_row = conn.execute(text(
            "SELECT n_cuentas, nombre_archivo FROM catalogo_empresa WHERE empresa_id=:e"),
            {"e": eid}).mappings().first()
    cat_estado = {"propio": bool(cat_row),
                  "n": cat_row["n_cuentas"] if cat_row else None,
                  "nombre": cat_row["nombre_archivo"] if cat_row else None,
                  "n_default": len(clf.cargar_catalogo(_catalogo_default_texto() or ""))}
    return tpl.TemplateResponse(request, "cargar.html", _ctx(
        request, emp=emp, fuente=fuente, com=com, bal=bal, agua=agua, costos=costos,
        ajuste_coc=ajuste_coc, ccp_fap=ccp_fap, servicios_emp=servicios_emp, cat_estado=cat_estado,
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
                      anio_tarifario: int = Form(...), mes: str = Form(""), q_m3: str = Form(""),
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
    mnum = "".join(ch for ch in (mes or "") if ch.isdigit())
    mnum = int(mnum) if mnum else 0
    if not (1 <= mnum <= 12):
        return RedirectResponse(_dest(next, dflt, "err=Indica+el+mes+(1-12)"), status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        bcr.serie_set(conn, eid, servicio, anio_tarifario, _fnum(q_m3), _fnum(cmi_cobrado),
                      int(seg) if seg else None, mes=mnum)
    db.audit(scope_of(user), "bcr_serie", "empresa", eid, f"{servicio} año {anio_tarifario} mes {mnum}")
    return RedirectResponse(_dest(next, dflt, "msg=Serie+688+guardada"), status_code=303)


@app.post("/empresa/{eid}/bcr-serie-csv")
def bcr_serie_csv(request: Request, eid: int,
                  archivos: list[UploadFile] = File(..., alias="archivos"),
                  next: str = Form(""), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    dflt = f"/empresa/{eid}/inversiones?sec=agua"
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(_dest(next, dflt, "err=No+autorizado"), status_code=303)
    tot_ok, errs, n_arch = 0, [], 0
    with db.scope_conn(scope_of(user)) as conn:
        if not _emp_or_redirect(conn, eid):
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        for arch in archivos:
            if not getattr(arch, "filename", ""):
                continue
            ok, err = bcr.cargar_serie_csv(conn, eid, _leer_csv(arch))
            tot_ok += ok; errs += (err or []); n_arch += 1
    db.audit(scope_of(user), "bcr_serie_csv", "empresa", eid, f"{n_arch} archivos, {tot_ok} filas, {len(errs)} errores")
    aviso = f"msg=Serie+688:+{n_arch}+archivo(s),+{tot_ok}+filas+cargadas"
    if errs:
        aviso += ";+" + ",+".join(errs[:3]).replace(" ", "+") + ("+…" if len(errs) > 3 else "")
    return RedirectResponse(_dest(next, dflt, aviso), status_code=303)


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
