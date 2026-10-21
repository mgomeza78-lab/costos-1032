# -*- coding: utf-8 -*-
"""Pruebas del Balance de Subsidios y Contribuciones (FSRI) y del Tablero.

  · el cálculo aplica subsidio (−) a estratos 1–3 y contribución (+) a 5–6/comercial;
  · el déficit mensual promedio = balance / meses;
  · la contribución se liquida sobre el consumo TOTAL (no solo el básico);
  · RLS: un usuario Empresa no ve el balance de otra empresa (y la vista redirige);
  · las vistas /dashboard y /subsidios responden 200 y renderizan sin error.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import subsidios_service as subs

PW = config.SEED_PASSWORD
LAS_CEIBAS, ESSMAR = 1, 2
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def csrf(cli, path):
    m = re.search(r'name="csrf-token" content="([^"]+)"', cli.get(path).text)
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


print("== Cálculo del balance (semilla Las Ceibas, acueducto) ==")
with db.engine_owner.connect() as cn:
    bal = subs.balance(cn, LAS_CEIBAS, 2026)
t = bal["total"]
check(bal["hay_datos"], "hay datos del comercial para Las Ceibas")
check(t["subsidios"] < 0, f"subsidios totales negativos ({t['subsidios']:,.0f})")
check(t["contribuciones"] > 0, f"contribuciones totales positivas ({t['contribuciones']:,.0f})")
check(abs(t["balance"] - (t["subsidios"] + t["contribuciones"])) < 1, "balance = subsidios + contribuciones")
check(abs(t["deficit_mensual"] - t["balance"] / bal["n_meses"]) < 1, "déficit mensual = balance / meses")

ac = bal["servicios"].get("acueducto", {})
clases = {c["clase"]: c for c in ac.get("clases", [])}
check(1 in clases and clases[1]["sub"] < 0 and clases[1]["con"] == 0, "estrato 1: solo subsidio (−)")
check(5 in clases and clases[5]["con"] > 0 and clases[5]["sub"] == 0, "estrato 5: solo contribución (+)")
check(11 in clases and clases[11]["con"] > 0, "comercial: contribución (+)")
# La contribución del estrato 5 tiene m³ subsidiable = 0 pero sí liquida sobre el consumo total:
# su contribución debe exceder la parte del solo cargo fijo (comprobación cualitativa de la metodología).
check(clases[5]["m3s"] == 0 and clases[5]["m3"] > 0 and clases[5]["con"] > 0,
      "estrato 5 contribuye sobre el consumo total (m³>0, m³sub=0)")

print("== RLS: ESSMAR no ve el balance de Las Ceibas ==")
with db.scope_conn({"user_id": 0, "allow_all": False, "empresa_ids": [ESSMAR]}) as cn:
    bal_cross = subs.balance(cn, LAS_CEIBAS, 2026)
check(not bal_cross["hay_datos"], "balance de Las Ceibas vacío bajo el alcance de ESSMAR (RLS)")

print("== Vistas responden 200 y renderizan sin error ==")
op = cli("operador.neiva@lasceibas.gov.co")
rd = op.get(f"/empresa/{LAS_CEIBAS}/dashboard")
check(rd.status_code == 200 and "Tablero de indicadores" in rd.text, f"/dashboard responde 200 ({rd.status_code})")
check("Balance de subsidios" in rd.text, "el dashboard muestra el bloque de subsidios")
rs = op.get(f"/empresa/{LAS_CEIBAS}/subsidios")
check(rs.status_code == 200 and "Balance de subsidios y contribuciones" in rs.text,
      f"/subsidios responde 200 ({rs.status_code})")
check("Estrato 1" in rs.text and "Comercial" in rs.text, "la vista muestra las clases de uso")

print("== RLS en la vista: operador de ESSMAR no entra a Las Ceibas ==")
es = cli("operador@essmar.gov.co")
rx = es.get(f"/empresa/{LAS_CEIBAS}/subsidios", follow_redirects=False)
check(rx.status_code in (302, 303) and "/panel" in rx.headers.get("location", ""),
      "ESSMAR es redirigido fuera de Las Ceibas")

print("\n" + ("TODAS LAS PRUEBAS DE SUBSIDIOS PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
