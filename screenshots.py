# -*- coding: utf-8 -*-
"""Capturas de la plataforma: aislamiento por rol + pantallas de seguridad."""
import os
import re
from playwright.sync_api import sync_playwright
from sqlalchemy import text
import db

BASE = "http://127.0.0.1:8000"
PW = os.environ.get("SEED_PASSWORD", "Cambiar2026*")
OUT = "/home/claude/app_1032/shots"
os.makedirs(OUT, exist_ok=True)


def login(page, email):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", PW)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


with sync_playwright() as p:
    b = p.chromium.launch()
    # --- Administrador ---
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    login(pg, "mgomeza78@gmail.com")
    pg.screenshot(path=f"{OUT}/01_panel_admin.png", full_page=True)
    pg.goto(f"{BASE}/empresa/1", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/02_empresa_lasceibas.png", full_page=True)
    pg.goto(f"{BASE}/usuarios", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/03_usuarios.png", full_page=True)
    pg.goto(f"{BASE}/permisos", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/04_permisos.png", full_page=True)
    pg.goto(f"{BASE}/empresa/1/mensual", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/10_mensual_lasceibas.png", full_page=True)
    pg.goto(f"{BASE}/ipc", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/11_ipc.png", full_page=True)
    # cuenta + MFA (sin persistir: solo muestra la pantalla de enrolamiento)
    pg.goto(f"{BASE}/cuenta", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/07_cuenta.png", full_page=True)
    pg.click("form[action='/cuenta/mfa/iniciar'] button")
    pg.wait_for_load_state("networkidle")
    pg.screenshot(path=f"{OUT}/08_cuenta_mfa_qr.png", full_page=True)
    ctx.close()
    # --- Usuario Empresa (ESSMAR) ---
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    login(pg, "operador@essmar.gov.co")
    pg.screenshot(path=f"{OUT}/05_panel_empresa_essmar.png", full_page=True)
    pg.goto(f"{BASE}/empresa/2", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/06_empresa_essmar.png", full_page=True)
    ctx.close()
    # --- login ---
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.screenshot(path=f"{OUT}/00_login.png", full_page=True)
    ctx.close()
    # --- segundo factor (MFA) en el login: activar temporalmente y revertir ---
    with db.engine_owner.begin() as conn:
        conn.execute(text("UPDATE usuario SET mfa_secret='JBSWY3DPEHPK3PXP', mfa_activo=true "
                          "WHERE email='analista@sictaa.co'"))
    try:
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        login(pg, "analista@sictaa.co")          # queda en /mfa
        pg.screenshot(path=f"{OUT}/09_mfa_login.png", full_page=True)
        ctx.close()
    finally:
        with db.engine_owner.begin() as conn:
            conn.execute(text("UPDATE usuario SET mfa_secret=NULL, mfa_activo=false "
                              "WHERE email='analista@sictaa.co'"))
    b.close()
print("capturas listas en", OUT)
