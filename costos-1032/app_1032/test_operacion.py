# -*- coding: utf-8 -*-
"""Pruebas de la capa de operación mensual (en proceso, vía TestClient).

  · el motor dispara el gatillo del 3 % en el mes correcto y mantiene la tarifa cuando no;
  · un usuario Empresa carga lo suyo pero NO puede cargar en otra empresa (RLS);
  · el Auditor no puede cargar ni procesar; el Administrador sí procesa.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db

PW = config.SEED_PASSWORD
LAS_CEIBAS, ESSMAR = 1, 2
_fail = []


def check(cond, desc):
    print(("  OK  " if cond else "FALLA ") + desc)
    if not cond:
        _fail.append(desc)


def csrf(client, path):
    html = client.get(path).text
    m = (re.search(r'name="csrf-token" content="([^"]+)"', html)
         or re.search(r'name="csrf" value="([^"]+)"', html))
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


# ---------- 1) motor de gatillo ----------
print("== Motor de indexación (gatillo 3%) ==")
with db.engine_owner.connect() as conn:
    base_cf = conn.execute(text(
        "SELECT valor FROM resultado_componente rc JOIN empresa e ON e.id=rc.empresa_id "
        "WHERE e.codigo='LAS_CEIBAS' AND rc.servicio='acueducto' AND rc.componente='CARGO_FIJO'")).scalar_one()
    rows = conn.execute(text(
        "SELECT tv.mes, tv.indexado, tv.cargo_fijo FROM tarifa_vigente tv JOIN empresa e ON e.id=tv.empresa_id "
        "WHERE e.codigo='LAS_CEIBAS' AND tv.servicio='acueducto' ORDER BY tv.mes")).mappings().all()
porm = {r["mes"]: r for r in rows}
check(not porm[10]["indexado"] and abs(porm[10]["cargo_fijo"] - base_cf) < 0.01,
      "oct (var 2,30%) NO indexa: tarifa = base")
check(porm[11]["indexado"] and abs(porm[11]["cargo_fijo"] - base_cf * 1.031) < 0.5,
      f"nov (var 3,10%) indexa: cargo fijo = base×1,031 ({porm[11]['cargo_fijo']:.2f})")
check(not porm[12]["indexado"] and abs(porm[12]["cargo_fijo"] - porm[11]["cargo_fijo"]) < 0.01,
      "dic mantiene la tarifa indexada (gatillo reiniciado)")

# ---------- 2) carga mensual con aislamiento ----------
print("== Carga mensual (RLS) ==")
essmar = cli("operador@essmar.gov.co")
# su propia empresa: OK
tok = csrf(essmar, f"/empresa/{ESSMAR}/mensual")
r = essmar.post(f"/empresa/{ESSMAR}/carga", follow_redirects=False,
                data={"anio": 2026, "mes": 8, "servicio": "acueducto", "suscriptores": "95000",
                      "m3": "1500000", "facturacion": "", "novedades": "prueba", "csrf": tok})
check("Carga+registrada" in r.headers.get("location", ""), "ESSMAR carga su propio mes")
# otra empresa (Las Ceibas): RLS lo rechaza
tok = csrf(essmar, f"/empresa/{ESSMAR}/mensual")
r = essmar.post(f"/empresa/{LAS_CEIBAS}/carga", follow_redirects=False,
                data={"anio": 2026, "mes": 8, "servicio": "acueducto", "suscriptores": "1",
                      "m3": "1", "csrf": tok})
check("No+se+pudo+cargar" in r.headers.get("location", ""),
      f"ESSMAR NO puede cargar en Las Ceibas ({r.headers.get('location')})")
# verificación en base: no se escribió fila de ESSMAR en Las Ceibas con susc=1
with db.engine_owner.connect() as conn:
    intruso = conn.execute(text(
        "SELECT count(*) FROM carga_mensual WHERE empresa_id=:e AND suscriptores=1"),
        {"e": LAS_CEIBAS}).scalar_one()
check(intruso == 0, "no quedó carga intrusa en Las Ceibas")

# ---------- 3) permisos de procesamiento ----------
print("== Permisos de indexación ==")
aud = cli("auditor@sspd.gov.co")
tok = csrf(aud, f"/empresa/{LAS_CEIBAS}/mensual")
r = aud.post(f"/empresa/{LAS_CEIBAS}/procesar", data={"csrf": tok}, follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), "auditor NO puede procesar indexación")
admin = cli("mgomeza78@gmail.com")
tok = csrf(admin, f"/empresa/{ESSMAR}/mensual")
r = admin.post(f"/empresa/{ESSMAR}/procesar", data={"csrf": tok}, follow_redirects=False)
check("procesada" in r.headers.get("location", ""), "admin procesa la indexación")

print("\n" + ("TODAS LAS PRUEBAS DE OPERACIÓN PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
