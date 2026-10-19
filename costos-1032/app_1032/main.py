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
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

import config, db, rbac, nucleo_service
import operacion_service as ops
import recalculo_service as rc
import inversiones_service as inv
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
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; form-action 'self'; frame-ancestors 'none'; "
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
    return RedirectResponse("/panel" if session_user(request) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if session_user(request):
        return RedirectResponse("/panel", status_code=303)
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
    destino = "/cuenta?msg=Debe+cambiar+su+contraseña" if u["debe_cambiar_pass"] else "/panel"
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
        return RedirectResponse("/panel", status_code=303)
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
        segs = conn.execute(text("SELECT id, nombre FROM segmento ORDER BY id")).mappings().all()
        existentes = {r0[0] for r0 in conn.execute(text("SELECT codigo FROM empresa")).all()}
    perfiles = [c for c in nucleo_service.codigos_disponibles() if c not in existentes]
    return tpl.TemplateResponse(request, "empresa_nueva.html", _ctx(request, segmentos=segs, perfiles=perfiles))


@app.post("/empresa-nueva")
def empresa_nueva_post(request: Request, codigo: str = Form(...), nombre: str = Form(""),
                       municipio: str = Form(""), segmento_id: int = Form(2),
                       presta_ac: str = Form(None), presta_al: str = Form(None),
                       fecha_688: str = Form(""), fecha_1032: str = Form(""),
                       tardia: str = Form(None), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "crear_empresa"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    codigo = codigo.strip().upper().replace(" ", "_")
    base = nucleo_service.perfil_resumen(codigo) if nucleo_service.perfil_existe(codigo) else {}
    data = {
        "codigo": codigo,
        "nombre": nombre.strip() or base.get("nombre") or codigo,
        "municipio": municipio.strip() or base.get("municipio"),
        "segmento_id": base.get("segmento") or segmento_id,
        "presta_ac": (presta_ac is not None) or bool(base.get("presta_ac")),
        "presta_al": (presta_al is not None) or bool(base.get("presta_al")),
        "esquema": base.get("esquema"),
        "r": base.get("r"), "kct": base.get("kct"),
        "f688": (base.get("fecha_inicio_688") or fecha_688 or None),
        "f1032": (base.get("fecha_inicio_1032") or fecha_1032 or None),
        "tardia": (tardia is not None) or bool(base.get("aplicacion_1032_tardia")),
    }
    try:
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO empresa (codigo,nombre,nit,municipio,segmento_id,presta_ac,presta_al,"
                " esquema,r,kct,fecha_inicio_688,fecha_inicio_1032,aplicacion_1032_tardia) "
                "VALUES (:codigo,:nombre,NULL,:municipio,:segmento_id,:presta_ac,:presta_al,"
                " :esquema,:r,:kct,:f688,:f1032,:tardia)"), data)
    except Exception as e:
        return RedirectResponse(f"/empresa-nueva?err=No+se+pudo+crear+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "crear_empresa", "empresa", None, codigo)
    return RedirectResponse("/panel?msg=Empresa+creada:+" + codigo, status_code=303)


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
    return tpl.TemplateResponse(request, "usuarios.html",
                                _ctx(request, usuarios=us, empresas=empresas, roles=roles,
                                     min_len=config.PASSWORD_MIN_LEN))


@app.post("/usuarios")
def usuarios_post(request: Request, email: str = Form(...), nombre: str = Form(...),
                  rol: str = Form(...), empresa_id: str = Form(""), password: str = Form(...),
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
    try:
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO usuario (email,nombre,password_hash,rol_id,empresa_id,activo,debe_cambiar_pass) "
                "VALUES (:em,:no,:ph,(SELECT id FROM rol WHERE codigo=:rc),:eid,true,true)"),
                {"em": email.strip().lower(), "no": nombre.strip(),
                 "ph": hash_password(password), "rc": rol, "eid": eid})
    except Exception as e:
        return RedirectResponse(f"/usuarios?err=No+se+pudo+crear+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "crear_usuario", "usuario", eid, f"{email} ({rol})")
    return RedirectResponse("/usuarios?msg=Credencial+emitida+(cambio+obligatorio):+" + email, status_code=303)


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
           origen: str = Form("archivo_propio"), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/mensual?err=No+autorizado", status_code=303)

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
        return RedirectResponse(f"/empresa/{eid}/mensual?err=No+se+pudo+cargar+({type(e).__name__})",
                                status_code=303)
    db.audit(scope_of(user), "carga_mensual", "empresa", eid, f"{ops.MESES.get(mes,mes)}-{anio} {servicio}")
    return RedirectResponse(f"/empresa/{eid}/mensual?msg=Carga+registrada", status_code=303)


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
               archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/mensual?err=No+autorizado", status_code=303)
    if tipo not in ingesta.TIPOS:
        return RedirectResponse(f"/empresa/{eid}/mensual?err=Tipo+inválido", status_code=303)
    contenido = _leer_csv(archivo)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT id FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        ok, err = ingesta.TIPOS[tipo](conn, eid, contenido)
        if tipo in ("comercial", "factores") and ok:
            ops.derivar_factura(conn, eid)
    db.audit(scope_of(user), "cargar_csv", "empresa", eid, f"{tipo}: {ok} filas, {len(err)} errores")
    aviso = f"{tipo}:+{ok}+filas+cargadas"
    if err:
        aviso += f";+{len(err)}+con+error+(" + ",+".join(err[:3]).replace(" ", "+") + ")"
    return RedirectResponse(f"/empresa/{eid}/mensual?msg={aviso}", status_code=303)


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
def cargar_balance(request: Request, eid: int, anio: int = Form(...), mes: int = Form(...),
                   archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "cargar_mensual"):
        return RedirectResponse(f"/empresa/{eid}/recalculo?err=No+autorizado", status_code=303)
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
            f"/empresa/{eid}/recalculo?err=No+se+pudo+leer+el+balance+({type(e).__name__})", status_code=303)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT codigo FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        cat_path = _catalogo_path(emp["codigo"])
        if not cat_path:
            return RedirectResponse(
                f"/empresa/{eid}/recalculo?err=Falta+el+catálogo+de+clasificación+de+esta+empresa",
                status_code=303)
        catalogo = clf.cargar_catalogo(open(cat_path, encoding="utf-8").read())
        sub, comp, sin = clf.clasificar(filas, catalogo)
        nums = clf.numeradores(sub)
        split = rc.split_servicio(conn, eid)
        n = ingesta.persistir_numeradores_mensual(conn, eid, anio, mes, nums, split)
        rc.recalcular(conn, eid)
    db.audit(scope_of(user), "cargar_balance", "empresa", eid,
             f"{ops.MESES.get(mes,mes)}-{anio}: {n} numeradores, {len(sin)} cuentas sin clasificar")
    aviso = f"Balance+{ops.MESES.get(mes,mes)}-{anio}:+numeradores+clasificados+y+recálculo+hecho"
    if sin:
        aviso += f";+{len(sin)}+cuentas+sin+clasificar"
    return RedirectResponse(f"/empresa/{eid}/recalculo?msg={aviso}", status_code=303)


@app.get("/empresa/{eid}/inversiones", response_class=HTMLResponse)
def inversiones(request: Request, eid: int):
    if (r := _need_login(request)):
        return r
    user = session_user(request)
    with db.scope_conn(scope_of(user)) as conn:
        emp = conn.execute(text("SELECT * FROM empresa WHERE id=:e"), {"e": eid}).mappings().first()
        if not emp:
            return RedirectResponse("/panel?err=Empresa+no+disponible", status_code=303)
        proyectos = inv.tablero(conn, eid)
        res = inv.resumen(conn, eid)
    return tpl.TemplateResponse(request, "inversiones.html", _ctx(
        request, emp=emp, proyectos=proyectos, resumen=res,
        clasificaciones=inv.CLASIFICACIONES, estados=inv.ESTADOS,
        comp_ac=inv.COMPONENTES_AC, comp_al=inv.COMPONENTES_AL,
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


@app.post("/ipc/cargar")
def ipc_cargar(request: Request, archivo: UploadFile = File(...), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    contenido = _leer_csv(archivo)
    with db.scope_conn(scope_of(user)) as conn:
        ok, err = ingesta.cargar_indices(conn, contenido)
    db.audit(scope_of(user), "cargar_ipc_csv", "ipc", None, f"{ok} filas, {len(err)} errores")
    aviso = f"IPC:+{ok}+filas"
    if err:
        aviso += f";+errores:+" + ",+".join(err[:3]).replace(" ", "+")
    return RedirectResponse(f"/ipc?msg={aviso}", status_code=303)


@app.get("/ipc", response_class=HTMLResponse)
def ipc_form(request: Request):
    if (r := _need_login(request)):
        return r
    if not rbac.can(session_user(request), "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    with db.scope_conn(scope_of(session_user(request))) as conn:
        filas = conn.execute(text(
            "SELECT anio, mes, indice, fuente, procedencia FROM indice_ipc "
            "ORDER BY anio, mes")).mappings().all()
    return tpl.TemplateResponse(request, "ipc.html", _ctx(request, filas=filas, meses=ops.MESES))


@app.post("/ipc")
def ipc_post(request: Request, anio: int = Form(...), mes: int = Form(...),
             indice: str = Form(...), fuente: str = Form("DANE"), csrf: str = Form("")):
    if (r := _need_login(request)):
        return r
    if (bad := _bad_csrf(request, csrf)):
        return bad
    user = session_user(request)
    if not rbac.can(user, "administrar_ipc"):
        return RedirectResponse("/panel?err=No+autorizado", status_code=303)
    try:
        val = float(indice.strip().replace(",", "."))
        with db.scope_conn(scope_of(user)) as conn:
            conn.execute(text(
                "INSERT INTO indice_ipc(anio,mes,indice,fuente,procedencia,cargado_por) "
                "VALUES (:a,:m,:v,:f,'reportada',:u) "
                "ON CONFLICT (anio,mes) DO UPDATE SET indice=excluded.indice, "
                " fuente=excluded.fuente, procedencia=excluded.procedencia, cargado_por=excluded.cargado_por"),
                {"a": anio, "m": mes, "v": val, "f": fuente.strip() or "DANE", "u": user["user_id"]})
    except Exception as e:
        return RedirectResponse(f"/ipc?err=No+se+pudo+guardar+({type(e).__name__})", status_code=303)
    db.audit(scope_of(user), "cargar_ipc", "ipc", None, f"{ops.MESES.get(mes,mes)}-{anio}={indice}")
    return RedirectResponse("/ipc?msg=IPC+guardado+(recuerde+reprocesar+la+indexación)", status_code=303)


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
