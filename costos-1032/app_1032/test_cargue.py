# -*- coding: utf-8 -*-
"""Pruebas del cargue de CSV y la factura por estrato (en proceso, vía TestClient).

  · ingesta válida carga filas y deriva factura; CSV inválido se rechaza;
  · un usuario Empresa NO puede cargar en otra empresa (RLS en el INSERT);
  · la factura por estrato aplica subsidio (−) a estratos bajos y contribución (+) arriba;
  · el Auditor no puede cargar.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db

PW = config.SEED_PASSWORD
LAS_CEIBAS, ESSMAR = 1, 2
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def csrf(cli, path):
    h = cli.get(path).text
    m = (re.search(r'name="csrf-token" content="([^"]+)"', h)
         or re.search(r'name="csrf" value="([^"]+)"', h))
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


def subir(c, eid, tipo, contenido):
    tok = csrf(c, f"/empresa/{eid}/mensual")
    return c.post(f"/empresa/{eid}/cargar-csv",
                  data={"tipo": tipo, "csrf": tok},
                  files={"archivos": (f"{tipo}.csv", contenido, "text/csv")},
                  follow_redirects=False)


essmar = cli("operador@essmar.gov.co")

print("== Ingesta válida (ESSMAR, su propia empresa) ==")
com = ("empresa,anio,mes,servicio,clase,suscriptores,m3,m3_subsidiable\n"
       "ESSMAR,2026,7,AC,1,20000,210000,180000\n"
       "ESSMAR,2026,7,AC,10,3000,70000,0\n")
r = subir(essmar, ESSMAR, "comercial", com)
check("2+filas+cargadas" in r.headers.get("location", ""), f"ESSMAR carga 2 filas comerciales ({r.headers.get('location')})")

fac = ("empresa,vigencia,servicio,clase,factor_cargofijo,factor_consumo\n"
       "ESSMAR,2026,AC,1,-0.70,-0.70\n"
       "ESSMAR,2026,AC,10,0.50,0.50\n")
r = subir(essmar, ESSMAR, "factores", fac)
check("2+filas+cargadas" in r.headers.get("location", ""), "ESSMAR carga 2 filas de factores")

print("== CSV inválido (falta columna) ==")
r = subir(essmar, ESSMAR, "comercial", "anio,mes,servicio\n2026,7,AC\n")
check("faltan+columnas" in r.headers.get("location", ""), "CSV sin columnas obligatorias es rechazado")

print("== Aislamiento: ESSMAR intenta cargar en Las Ceibas ==")
intruso = ("empresa,anio,mes,servicio,clase,suscriptores,m3,m3_subsidiable\n"
           "LAS_CEIBAS,2026,7,AC,99,7,7,0\n")
r = subir(essmar, LAS_CEIBAS, "comercial", intruso)
loc = r.headers.get("location", "")
check("0+filas" in loc or "error" in loc or "no+disponible" in loc,
      f"carga cruzada bloqueada ({loc})")
with db.engine_owner.connect() as cn:
    n = cn.execute(text("SELECT count(*) FROM carga_mensual_detalle WHERE empresa_id=:e AND clase=99"),
                   {"e": LAS_CEIBAS}).scalar_one()
check(n == 0, "no quedó fila intrusa (clase 99) en Las Ceibas")

print("== Factura por estrato: subsidio (−) y contribución (+) ==")
with db.engine_owner.connect() as cn:
    sub1 = cn.execute(text("SELECT subsidio_contribucion FROM factura_clase WHERE empresa_id=:e "
                           "AND servicio='acueducto' AND clase=1 AND anio=2026 AND mes=7"),
                      {"e": ESSMAR}).scalar()
    sub10 = cn.execute(text("SELECT subsidio_contribucion FROM factura_clase WHERE empresa_id=:e "
                            "AND servicio='acueducto' AND clase=10 AND anio=2026 AND mes=7"),
                       {"e": ESSMAR}).scalar()
check(sub1 is not None and sub1 < 0, f"estrato 1: subsidio negativo ({sub1})")
check(sub10 is not None and sub10 > 0, f"comercial: contribución positiva ({sub10})")

print("== Auditor no puede cargar ==")
aud = cli("auditor@sspd.gov.co")
r = subir(aud, LAS_CEIBAS, "comercial", com)
check("No+autorizado" in r.headers.get("location", ""), "auditor rechazado al cargar")

print("== Importar archivo ORIGINAL del SUI (agrega por clase) ==")
ac_sui = ("NUID_1,CLASEUSO_16,LECT_CONSUMO_26,CONS_SUB_27,FACTORSUBSIDIOCARGOFIJO_33,FACTORSUBSIDIOCONSUMO_35\n"
          "1,1,10,8,0,-0.54\n2,1,12,9,0,-0.54\n3,11,50,0,1.0,0.6\n")
tok = csrf(essmar, f"/empresa/{ESSMAR}/mensual")
r = essmar.post(f"/empresa/{ESSMAR}/cargar-sui",
                data={"servicio": "acueducto", "anio": 2026, "mes": 8, "csrf": tok},
                files={"archivo": ("Facturacion AC.csv", ac_sui, "text/csv")}, follow_redirects=False)
check("2+clases" in r.headers.get("location", ""), f"SUI AC agrega 2 clases ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    susc1 = cn.execute(text("SELECT suscriptores FROM carga_mensual_detalle WHERE empresa_id=:e "
                            "AND servicio='acueducto' AND anio=2026 AND mes=8 AND clase=1"),
                       {"e": ESSMAR}).scalar()
check(susc1 == 2, f"clase 1 agregó 2 suscriptores ({susc1})")
# archivo de servicio equivocado
tok = csrf(essmar, f"/empresa/{ESSMAR}/mensual")
r = essmar.post(f"/empresa/{ESSMAR}/cargar-sui",
                data={"servicio": "alcantarillado", "anio": 2026, "mes": 8, "csrf": tok},
                files={"archivo": ("x.csv", ac_sui, "text/csv")}, follow_redirects=False)
check("no+se+hallaron+columnas" in r.headers.get("location", ""), "archivo de servicio equivocado se rechaza")

print("\n" + ("TODAS LAS PRUEBAS DE CARGUE PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
