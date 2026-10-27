# -*- coding: utf-8 -*-
"""Pruebas de la página de índices / indexación:

  · varios índices mensuales (IPC, IPC-SAR, ICTC) en indice_ipc + salario anual;
  · ingreso mensual (IPC obligatorio; IPC-SAR/ICTC opcionales con COALESCE);
  · salario mínimo anual (un valor por año) y parseo de miles;
  · variaciones mensual/acumulada y 'próximo a cargar';
  · autorización (solo administrar_ipc) y compatibilidad con la indexación/BCR.

Usa un rango de años ficticio (2098–2099) y lo limpia al final, para no tocar
los datos reales ni la indexación del período de inicio.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db, indices_service as ix
import operacion_service as ops
import bcr_service as bcr

PW = config.SEED_PASSWORD
_fail = []


def check(c, d):
    print(("  OK  " if c else "FALLA ") + d)
    if not c:
        _fail.append(d)


def near(a, b, t=0.01):
    return a is not None and abs(a - b) <= t


def csrf(cli, path="/ipc"):
    m = re.search(r'name="csrf-token" content="([^"]+)"', cli.get(path).text)
    return m.group(1) if m else ""


def cli(email):
    c = TestClient(main.app)
    c.post("/login", data={"email": email, "password": PW, "csrf": csrf(c, "/login")},
           follow_redirects=False)
    return c


def q(sql, **p):
    with db.engine_owner.begin() as conn:
        return conn.execute(text(sql), p).all()


def limpiar():
    with db.engine_owner.begin() as c:
        c.execute(text("DELETE FROM indice_ipc WHERE anio IN (2098, 2099)"))
        c.execute(text("DELETE FROM salario_minimo WHERE anio IN (2098, 2099)"))


limpiar()
admin = cli("mgomeza78@gmail.com")

# ---------- 1) la página carga ----------
print("== Página de índices ==")
html = admin.get("/ipc").text
check(admin.get("/ipc").status_code == 200, "GET /ipc responde 200 al admin")
check("Último dato cargado" in html, "muestra el bloque 'Último dato cargado'")
check("Evolución" in html and "<svg" in html, "muestra la gráfica (SVG)")
check("Ingresar / actualizar índices" in html and "Salario mínimo (anual)" in html, "formularios de ingreso presentes")
check("Cargar CSV" not in html and "CSV" not in html, "ya NO hay carga masiva (CSV)")

# ---------- 2) base + ingreso mensual por la ruta ----------
print("== Ingreso mensual ==")
with db.engine_owner.begin() as c:   # punto base anterior a la ventana
    c.execute(text("INSERT INTO indice_ipc(anio,mes,indice) VALUES (2098,12,100.0) "
                   "ON CONFLICT (anio,mes) DO UPDATE SET indice=excluded.indice"))
r = admin.post("/ipc", data={"anio": 2099, "mes": 1, "indice": "102,00",
               "ipcs": "101,00", "ictc": "103,00", "fuente": "DANE", "csrf": csrf(admin)},
               follow_redirects=False)
check("guardado" in r.headers.get("location", ""), "guarda el dato mensual")
row = q("SELECT indice,ipcs,ictc FROM indice_ipc WHERE anio=2099 AND mes=1")[0]
check(near(float(row[0]), 102.0) and near(float(row[1]), 101.0) and near(float(row[2]), 103.0),
      f"IPC/IPC-SAR/ICTC almacenados (obtenido {tuple(float(x) for x in row)})")

# segundo mes (para variaciones)
admin.post("/ipc", data={"anio": 2099, "mes": 2, "indice": "103,02", "ipcs": "", "ictc": "",
           "csrf": csrf(admin)}, follow_redirects=False)

# ---------- 3) COALESCE: actualizar solo IPC no borra IPC-SAR/ICTC ----------
print("== Actualización parcial (COALESCE) ==")
admin.post("/ipc", data={"anio": 2099, "mes": 1, "indice": "102,50", "ipcs": "", "ictc": "",
           "csrf": csrf(admin)}, follow_redirects=False)
row = q("SELECT indice,ipcs,ictc FROM indice_ipc WHERE anio=2099 AND mes=1")[0]
check(near(float(row[0]), 102.5) and near(float(row[1]), 101.0) and near(float(row[2]), 103.0),
      "al reenviar solo IPC, IPC-SAR e ICTC se conservan")

# ---------- 4) carga por separado (cada índice publica en fecha distinta) ----------
print("== Carga por separado de cada índice ==")
r = admin.post("/ipc", data={"anio": 2099, "mes": 6, "indice": "", "ipcs": "", "ictc": "",
               "csrf": csrf(admin)}, follow_redirects=False)
check("err=" in r.headers.get("location", ""), "sin ningún índice se rechaza")
check(not q("SELECT 1 FROM indice_ipc WHERE anio=2099 AND mes=6"), "no se creó la fila vacía")
# solo ICTC (el IPC de ese mes aún no publica): se guarda con IPC nulo
admin.post("/ipc", data={"anio": 2099, "mes": 6, "indice": "", "ipcs": "", "ictc": "150,00",
           "csrf": csrf(admin)}, follow_redirects=False)
row6 = q("SELECT indice, ictc FROM indice_ipc WHERE anio=2099 AND mes=6")
check(bool(row6) and row6[0][0] is None and near(float(row6[0][1]), 150.0),
      "carga solo-ICTC crea la fila con IPC nulo e ICTC=150")
# luego llega el IPC del mismo mes: no borra el ICTC ya cargado (COALESCE en los tres)
admin.post("/ipc", data={"anio": 2099, "mes": 6, "indice": "104,00", "ipcs": "", "ictc": "",
           "csrf": csrf(admin)}, follow_redirects=False)
row6b = q("SELECT indice, ictc FROM indice_ipc WHERE anio=2099 AND mes=6")[0]
check(near(float(row6b[0]), 104.0) and near(float(row6b[1]), 150.0),
      "cargar el IPC después conserva el ICTC (COALESCE)")
with db.engine_owner.begin() as _c:
    _c.execute(text("DELETE FROM indice_ipc WHERE anio=2099 AND mes=6"))

# ---------- 5) variaciones y gráfica ----------
print("== Variaciones y gráfica ==")
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    g = ix.datos_grafica(conn, "indice", (2099, 1), (2099, 2))
    p1, p2 = g["puntos"][0], g["puntos"][1]
    check(near(p1["var_mes"], 2.5) and near(p1["var_acum"], 2.5),
          f"ene-2099: var.mensual y acumulada = +2.5% (base 100) (obtenido {p1['var_mes']:.2f}/{p1['var_acum']:.2f})")
    check(near(p2["var_mes"], 0.507, 0.02) and near(p2["var_acum"], 3.02),
          f"feb-2099: var.mensual ~+0.51% y acumulada +3.02% (obtenido {p2['var_mes']:.3f}/{p2['var_acum']:.3f})")
    check(ix.svg_grafica(g).startswith("<svg"), "la gráfica genera SVG")
    check(ix.proximo_mes(conn) == (2099, 3), f"próximo mes a cargar = mar-2099 (obtenido {ix.proximo_mes(conn)})")

# ---------- 6) salario mínimo anual ----------
print("== Salario mínimo (anual) ==")
admin.post("/ipc/salario", data={"anio": 2098, "valor": "2.000.000", "fuente": "Decreto X",
           "csrf": csrf(admin)}, follow_redirects=False)
r = admin.post("/ipc/salario", data={"anio": 2099, "valor": "2.200.000", "fuente": "Decreto Y",
               "csrf": csrf(admin)}, follow_redirects=False)
check("Salario" in r.headers.get("location", ""), "guarda el salario mínimo")
sm = q("SELECT valor FROM salario_minimo WHERE anio=2099")[0]
check(near(float(sm[0]), 2200000.0, 1), f"'2.200.000' se parsea a 2200000 (obtenido {float(sm[0])})")
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    serie = {s["anio"]: s for s in ix.salario_serie(conn)}
    check(near(serie[2099]["var"], 10.0), f"variación anual SMMLV = +10% (obtenido {serie[2099]['var']})")
    check(ix.proximo_anio_salario(conn) == 2100, "próximo año de salario = 2100")

# ---------- 7) autorización ----------
print("== Autorización ==")
op = cli("operador.neiva@lasceibas.gov.co")
check(op.get("/ipc", follow_redirects=False).status_code in (302, 303), "un operador NO ve /ipc")
r = op.post("/ipc", data={"anio": 2099, "mes": 7, "indice": "200", "csrf": csrf(op, "/empresa/1")},
            follow_redirects=False)
check("No+autorizado" in r.headers.get("location", ""), "un operador NO puede cargar índices")
check(not q("SELECT 1 FROM indice_ipc WHERE anio=2099 AND mes=7"), "no se cargó el índice del operador")

# ---------- 8) compatibilidad con indexación y BCR ----------
print("== Compatibilidad hacia atrás ==")
with db.scope_conn({"allow_all": True, "empresa_ids": [], "user_id": 1}) as conn:
    s = ops.serie_ipc(conn)
    check((2099, 1) in s and near(s[(2099, 1)][0], 102.5), "operacion_service.serie_ipc lee IPC (incl. 2099)")
    dic25 = bcr.ipc_dic(conn, 2025)
    check(dic25 is not None and dic25 > 0, f"bcr_service.ipc_dic(2025) sigue devolviendo IPC ({dic25})")

limpiar()
print()
if _fail:
    print(f"RESULTADO: {len(_fail)} comprobación(es) fallida(s)")
    for f in _fail:
        print("   - " + f)
    raise SystemExit(1)
print("RESULTADO: todas las comprobaciones pasaron.")
