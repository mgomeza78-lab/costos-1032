# -*- coding: utf-8 -*-
"""Pruebas de la vista CCP (Consumo Corregido por Pérdidas):

  · indicadores por unidad de facturación: ICUF=AF/N, IPUF real=(AP−AF)/N, ISUF=AP/N=ICUF+IPUF;
  · IPUF aplicado = mín(IPUF real, IPUF*) y CCP = AF + pérdidas reconocidas (caso tope activo);
  · alcantarillado sin macromedición: CCP = AF, sin IPUF/ISUF;
  · senda del IPUF* por año tarifario (segundo segmento = 6,6,6,5,5,4);
  · la ruta /empresa/{id}/ccp responde 200.

Usa el año ficticio 2097 en Las Ceibas (empresa 1, segundo segmento) y limpia al final.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db, ccp_view as cv

PW = config.SEED_PASSWORD
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def near(a, b, t=0.01):
    return a is not None and abs(a - b) <= t


def ex(sql, **p):
    with db.engine_owner.begin() as conn:
        conn.execute(text(sql), p)


def limpiar():
    ex("DELETE FROM carga_mensual WHERE empresa_id=1 AND anio=2097")
    ex("DELETE FROM macromedicion WHERE empresa_id=1 AND anio=2097")


limpiar()
# datos controlados: N=1000, AF=15000, AP=24000  (IPUF real=9 > tope 6 -> aplica el tope)
ex("INSERT INTO carga_mensual(empresa_id,anio,mes,servicio,suscriptores,m3_facturados,origen) "
   "VALUES (1,2097,1,'acueducto',1000,15000,'test')")
ex("INSERT INTO macromedicion(empresa_id,anio,mes,servicio,punto,m3_producido,origen) "
   "VALUES (1,2097,1,'acueducto','PX',24000,'test')")
# alcantarillado sin macromedición
ex("INSERT INTO carga_mensual(empresa_id,anio,mes,servicio,suscriptores,m3_facturados,origen) "
   "VALUES (1,2097,1,'alcantarillado',800,12000,'test')")

print("== Indicadores y CCP (acueducto, tope activo) ==")
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    r = cv.resumen(conn, 1, 2097)
    ac = r["indicadores"]["acueducto"]
    check(near(ac["icuf"], 15.0), f"ICUF = AF/N = 15,0 (obtenido {ac['icuf']})")
    check(near(ac["ipuf_real"], 9.0), f"IPUF real = (AP−AF)/N = 9,0 (obtenido {ac['ipuf_real']})")
    check(near(ac["isuf"], 24.0) and near(ac["isuf"], ac["icuf"] + ac["ipuf_real"]),
          f"ISUF = AP/N = 24,0 = ICUF+IPUF (obtenido {ac['isuf']})")
    check(near(r["ipuf_estrella"], 6.0), "IPUF* del segmento = 6,0")
    check(near(ac["ipuf_aplicado"], 6.0), f"IPUF aplicado = mín(9; 6) = 6,0 (obtenido {ac['ipuf_aplicado']})")
    check(near(ac["reconocidas"], 6000.0), f"pérdidas reconocidas = 6·N = 6000 (obtenido {ac['reconocidas']})")
    check(near(ac["ccp"], 21000.0), f"CCP = AF + reconocidas = 21000 (obtenido {ac['ccp']})")

    print("== Alcantarillado sin macromedición ==")
    al = r["indicadores"]["alcantarillado"]
    check(al["ipuf_real"] is None and al["isuf"] is None, "sin AP: IPUF e ISUF no aplican")
    check(near(al["ccp"], 12000.0), f"CCP = AF = 12000 (obtenido {al['ccp']})")
    check(near(al["icuf"], 15.0), "ICUF del alcantarillado = AF/N = 15,0")

    print("== Senda del IPUF* por año tarifario ==")
    sd = r["senda"]
    check(sd["conocida"] and [x["ipuf"] for x in sd["filas"]] == [6, 6, 6, 6, 5, 5, 4],
          f"senda 2.º segmento: inicio + 6,6,6,5,5,4 (obtenido {[x['ipuf'] for x in sd['filas']]})")
    check(sd["filas"][0]["calculado"] is True and sd["filas"][1]["calculado"] is False,
          "solo el período de inicio queda marcado como calculado")

print("== Ruta ==")
c = TestClient(main.app)
m = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/login").text)
c.post("/login", data={"email": "mgomeza78@gmail.com", "password": PW, "csrf": m.group(1)},
       follow_redirects=False)
check(c.get("/empresa/1/ccp?anio=2097").status_code == 200, "GET /empresa/1/ccp responde 200")
html = c.get("/empresa/1/ccp?anio=2097").text
check("Consumo Corregido por Pérdidas" in html and "ISUF" in html and "IPUF aplicado" in html,
      "la página muestra CCP, ISUF e IPUF aplicado")

limpiar()
print()
if _fail:
    print(f"RESULTADO: {len(_fail)} comprobación(es) fallida(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
