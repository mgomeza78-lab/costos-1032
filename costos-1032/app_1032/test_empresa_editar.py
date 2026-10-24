# -*- coding: utf-8 -*-
"""Pruebas de la pantalla de inicio por rol y de la edición de empresas ya creadas.

  · entrada tras el login: admin/analista → panel; empresa/auditor → su empresa;
  · permiso editar_empresa: admin y analista sí; empresa y auditor no;
  · reconciliación de municipios/APS al editar (quitar Piedecuesta de AMB y dejar
    3 APS de solo acueducto);
  · la edición NO destruye el detalle del APS ya configurado (georreferenciación,
    ordenamiento): solo refresca el servicio.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db

PW = config.SEED_PASSWORD
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


def destino(c):
    return c.get("/", follow_redirects=False).headers.get("location", "")


print("== Pantalla de inicio por rol ==")
check(destino(cli("mgomeza78@gmail.com")) == "/panel", "admin entra al panel de empresas")
check(destino(cli("analista@sictaa.co")) == "/panel", "analista entra al panel de empresas")
check(destino(cli("operador.neiva@lasceibas.gov.co")) == "/empresa/1", "operador de Las Ceibas entra directo a /empresa/1")
check(destino(cli("operador@essmar.gov.co")) == "/empresa/2", "operador de ESSMAR entra directo a /empresa/2")
check(destino(cli("auditor@sspd.gov.co")) == "/empresa/1", "auditor entra directo a su empresa asignada")

print("== Permiso para editar empresas ==")
ana = cli("analista@sictaa.co")
check(ana.get("/empresa/3/editar").status_code == 200, "el analista abre el formulario de edición (200)")
amb_op = cli("operador@amb.com.co")
r = amb_op.get("/empresa/3/editar", follow_redirects=False)
check(r.status_code in (302, 303), "el operador de empresa NO puede editar (redirigido)")

print("== Edición de AMB: 3 APS de solo acueducto (se retira Piedecuesta) ==")
adm = cli("mgomeza78@gmail.com")
tok = csrf(adm, "/empresa/3/editar")
r = adm.post("/empresa/3/editar", data={
    "csrf": tok, "nombre": "Acueducto Metropolitano de Bucaramanga S.A. E.S.P.",
    "suscriptores": "400000", "codigo_sui": "",
    "fecha_688": "2016-07-01", "fecha_1032": "2026-07-01",
    "aps": ["68001:ac", "68276:ac", "68307:ac"]}, follow_redirects=False)
check("/aps" in r.headers.get("location", ""), f"al guardar lleva a la configuración de APS ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    emp = cn.execute(text("SELECT segmento_id,n_aps,presta_ac,presta_al FROM empresa WHERE id=3")).mappings().first()
    muni = {x[0] for x in cn.execute(text("SELECT cod_dane FROM empresa_municipio WHERE empresa_id=3")).all()}
    apsrows = cn.execute(text("SELECT cod_dane,servicios FROM aps WHERE empresa_id=3 ORDER BY cod_dane")).mappings().all()
check(emp["segmento_id"] == 1, f"segmento recalculado = 1 ({emp['segmento_id']})")
check(emp["n_aps"] == 3, f"n_aps = 3 ({emp['n_aps']})")
check(emp["presta_ac"] and not emp["presta_al"], "AMB queda solo acueducto (presta_ac=t, presta_al=f)")
check(muni == {"68001", "68276", "68307"}, f"municipios = Bucaramanga/Floridablanca/Girón; Piedecuesta retirado ({sorted(muni)})")
check(len(apsrows) == 3 and all(a["servicios"] == "ac" for a in apsrows), "3 APS creados con servicio 'ac'")

print("== La edición conserva el detalle del APS ya configurado ==")
with db.engine_owner.begin() as cn:
    # se simula que Neiva ya tenía detalle cargado (georreferenciación + POT)
    cn.execute(text("UPDATE aps SET georref_presentada=true, instrumento_ot='POT' "
                    "WHERE empresa_id=1 AND cod_dane='41001'"))
tok = csrf(adm, "/empresa/1/editar")
adm.post("/empresa/1/editar", data={
    "csrf": tok, "nombre": "Las Ceibas E.P. de Neiva E.S.P.", "suscriptores": "112000",
    "codigo_sui": "", "fecha_688": "2016-07-01", "fecha_1032": "2026-07-01",
    "aps": ["41001:ambos", "41524:ac"]}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    neiva = cn.execute(text("SELECT servicios,georref_presentada,instrumento_ot FROM aps "
                            "WHERE empresa_id=1 AND cod_dane='41001'")).mappings().first()
check(neiva["georref_presentada"] is True and neiva["instrumento_ot"] == "POT",
      "el detalle del APS de Neiva (georreferenciación + POT) se conservó")
check(neiva["servicios"] == "ambos", "el servicio de Neiva sigue siendo 'ambos'")

# ---- restauración del estado sembrado (para re-ejecuciones) ----
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM aps WHERE empresa_id=3"))
    cn.execute(text("DELETE FROM empresa_municipio WHERE empresa_id=3"))
    for c0 in ("68001", "68276", "68307", "68547"):
        cn.execute(text("INSERT INTO empresa_municipio(empresa_id,cod_dane) VALUES (3,:c) ON CONFLICT DO NOTHING"),
                   {"c": c0})
    cn.execute(text("UPDATE empresa SET n_aps=1,segmento_id=1,presta_ac=true,presta_al=false,"
                    "suscriptores_seg=NULL WHERE id=3"))
    cn.execute(text("UPDATE aps SET numero_aps=NULL,georref_presentada=false,instrumento_ot=NULL "
                    "WHERE empresa_id=1 AND cod_dane='41001'"))
    cn.execute(text("UPDATE aps SET numero_aps=NULL WHERE empresa_id=1 AND cod_dane='41524'"))
    cn.execute(text("UPDATE empresa SET n_aps=2,suscriptores_seg=112000 WHERE id=1"))

print("\n" + ("TODAS LAS PRUEBAS DE EDICIÓN PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
