# -*- coding: utf-8 -*-
"""Pruebas de territorio (DIVIPOLA), segmentación y alta de empresa mejorada.

  · segmento por suscriptores en los límites (art. 2.1.2.1.1.6 de la Res. CRA 1032);
  · alta de empresa con varios municipios → empresa_municipio + segmento automático;
  · carga de DIVIPOLA desde CSV (upsert, con encabezados del DANE);
  · RLS/roles: un operador no puede crear empresa;
  · la vista /empresa-nueva responde 200 con los campos nuevos.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import territorio_service as terr

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


print("== Segmentación por suscriptores (límites CRA 1032) ==")
casos = [(400000, 1), (300001, 1), (300000, 2), (90001, 2), (90000, 3),
         (17001, 3), (17000, 4), (5001, 4), (5000, None), (1200, None)]
with db.engine_owner.connect() as cn:
    for n, esp in casos:
        sid, _ = terr.segmento_por_suscriptores(cn, n)
        check(sid == esp, f"{n:>7} suscriptores → segmento {sid} (esperado {esp})")

print("== Alta de empresa con varios municipios (admin) ==")
with db.engine_owner.begin() as _cn:
    _cn.execute(text("DELETE FROM empresa WHERE codigo='REGIONAL_TEST'"))
adm = cli("mgomeza78@gmail.com")
tok = csrf(adm, "/empresa-nueva")
r = adm.post("/empresa-nueva", data={
    "codigo": "REGIONAL_TEST", "nombre": "Regional de prueba", "suscriptores": "120000",
    "codigo_sui": "99999",
    "aps": ["68001:ambos", "68276:ambos", "41001:ac"], "csrf": tok},
    follow_redirects=False)
check("Empresa+creada" in r.headers.get("location", ""), f"empresa creada ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT id, segmento_id, n_aps, codigo_sui, suscriptores_seg, municipio, "
                          "presta_ac, presta_al FROM empresa WHERE codigo='REGIONAL_TEST'")).mappings().first()
    check(row is not None, "la empresa quedó registrada")
    if row:
        check(row["segmento_id"] == 2, f"segmento automático por suscriptores = 2 ({row['segmento_id']})")
        check(row["n_aps"] == 3 and row["codigo_sui"] == "99999" and row["suscriptores_seg"] == 120000,
              "n_aps (= municipios), código SUI y suscriptores guardados")
        check(row["presta_ac"] and row["presta_al"], "presta_ac/presta_al derivados de los servicios por APS")
        nmun = cn.execute(text("SELECT count(*) FROM empresa_municipio WHERE empresa_id=:e"),
                          {"e": row["id"]}).scalar_one()
        check(nmun == 3, f"3 municipios asignados ({nmun})")
        naps = cn.execute(text("SELECT count(*) FROM aps WHERE empresa_id=:e"), {"e": row["id"]}).scalar_one()
        check(naps == 3, f"3 APS creados con sus servicios ({naps})")
        serv_neiva = cn.execute(text("SELECT servicios FROM aps WHERE empresa_id=:e AND cod_dane='41001'"),
                                {"e": row["id"]}).scalar()
        check(serv_neiva == "ac", f"el APS de Neiva quedó con servicio 'ac' ({serv_neiva})")
        check(row["municipio"] and "(" in row["municipio"], f"municipio principal fijado ({row['municipio']})")

print("== DIVIPOLA cargada como tabla del sistema ==")
with db.engine_owner.connect() as cn:
    ndep = cn.execute(text("SELECT count(*) FROM departamento")).scalar_one()
    nmun = cn.execute(text("SELECT count(*) FROM municipio")).scalar_one()
    neiva = cn.execute(text("SELECT nombre FROM municipio WHERE cod_dane='41001'")).scalar()
check(ndep == 33, f"33 departamentos en el sistema ({ndep})")
check(nmun >= 1100, f"municipios del DANE en el sistema ({nmun})")
check(neiva == "Neiva", f"41001 = Neiva ({neiva})")

print("== Roles: un operador no puede crear empresa ==")
op = cli("operador.neiva@lasceibas.gov.co")
r = op.get("/empresa-nueva", follow_redirects=False)
check(r.status_code in (302, 303), "operador redirigido fuera de /empresa-nueva (sin permiso)")

print("== Vista /empresa-nueva renderiza con los campos nuevos ==")
rd = adm.get("/empresa-nueva")
check(rd.status_code == 200 and "Municipios atendidos" in rd.text and "Suscriptores" in rd.text,
      f"/empresa-nueva responde 200 con campos nuevos ({rd.status_code})")

print("\n" + ("TODAS LAS PRUEBAS DE TERRITORIO PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
