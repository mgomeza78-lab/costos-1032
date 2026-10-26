# -*- coding: utf-8 -*-
"""Pruebas de la dimensión APS en el cargue de agua producida (macromedición).

  · cargue masivo con columna `aps` (por nombre de municipio y por código DANE) + fila conjunto;
  · resolución de APS a cod_dane y coexistencia de filas por-APS y conjunto en el mismo mes/punto;
  · APS no reconocida → la fila se descarta con error, sin tumbar las demás;
  · cargue manual con cod_dane;
  · vista «Cargado»: columna APS y orden cronológico;
  · eliminación de una sola APS (no borra el conjunto ni las otras APS).
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db

PW = config.SEED_PASSWORD
EID = 1          # Las Ceibas (Neiva 41001 + Palermo 41524)
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


# Solo tocamos NUESTROS puntos de prueba; no borramos la macromedición de muestra sembrada
# (de la que dependen otras suites, p. ej. test_recalculo).
MIS = ("P1", "P2", "P9")
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM macromedicion WHERE empresa_id=:e AND punto = ANY(:p)"),
               {"e": EID, "p": list(MIS)})

adm = cli("mgomeza78@gmail.com")
N = f"/empresa/{EID}/cargar?fuente=agua"
tok = csrf(adm, N)

print("== Cargue masivo con columna APS (nombre, DANE y conjunto) ==")
csv_txt = (
    "anio,mes,servicio,punto,m3_producido,aps\n"
    "2024,7,acueducto,P1,1000000,Neiva\n"          # por nombre -> 41001
    "2024,7,acueducto,P1,500000,41524\n"            # por DANE   -> 41524 (Palermo)
    "2024,7,acueducto,P1,1500000,\n"                # vacío      -> conjunto ''
    "2024,8,acueducto,P1,900000,neiva\n"            # nombre en minúsculas
    "2024,7,acueducto,P9,42,Bogotá\n"               # APS ajena -> error, se descarta
)
r = adm.post(f"/empresa/{EID}/cargar-csv",
             data={"csrf": tok, "next": N, "tipo": "macromedicion"},
             files={"archivos": ("agua.csv", csv_txt, "text/csv")},
             follow_redirects=False)
check(r.status_code in (302, 303), f"POST cargar-csv responde redirección ({r.status_code})")

with db.engine_owner.connect() as cn:
    filas = cn.execute(text(
        "SELECT anio, mes, punto, cod_dane, m3_producido FROM macromedicion "
        "WHERE empresa_id=:e AND punto = ANY(:p) ORDER BY anio, mes, cod_dane"),
        {"e": EID, "p": list(MIS)}).mappings().all()
porcd = {}
for f in filas:
    porcd.setdefault(f["cod_dane"], 0)
    porcd[f["cod_dane"]] += 1
check(porcd.get("41001", 0) == 2, f"2 filas para Neiva (41001): jul y ago ({porcd.get('41001')})")
check(porcd.get("41524", 0) == 1, f"1 fila para Palermo (41524) ({porcd.get('41524')})")
check(porcd.get("", 0) == 1, f"1 fila conjunto (cod_dane '') ({porcd.get('')})")
check(all(f["punto"] != "P9" for f in filas), "la fila con APS ajena (Bogotá) se descartó")
# Coexistencia: mismo mes/punto (2024-07, P1) con tres APS distintas
jul_p1 = [f for f in filas if f["anio"] == 2024 and f["mes"] == 7 and f["punto"] == "P1"]
check(len(jul_p1) == 3, f"jul-2024/P1 coexisten 3 APS (41001, 41524, conjunto) ({len(jul_p1)})")

print("== Cargue manual con cod_dane ==")
adm.post(f"/empresa/{EID}/carga-agua", data={
    "csrf": tok, "next": N, "anio": "2024", "mes": "9", "servicio": "acueducto",
    "punto": "P2", "m3_producido": "777777", "cod_dane": "41001"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    man = cn.execute(text(
        "SELECT cod_dane, m3_producido FROM macromedicion WHERE empresa_id=:e AND punto='P2'"),
        {"e": EID}).mappings().first()
check(man is not None and man["cod_dane"] == "41001" and abs((man["m3_producido"] or 0) - 777777) < 1,
      "manual guardó el punto con su APS (41001)")

print("== Vista «Cargado»: columna APS + municipios ==")
html = adm.get(N).text
check("APS" in html and "Neiva" in html and "Palermo" in html, "la vista muestra la columna APS y los municipios")
check("Conjunto" in html, "la vista rotula la fila sin APS como «Conjunto»")

print("== Eliminar una sola APS no borra el conjunto ni las otras ==")
adm.post(f"/empresa/{EID}/cargue-eliminar", data={
    "csrf": tok, "next": N, "concepto": "agua", "anio": "2024", "mes": "7",
    "servicio": "acueducto", "cod_dane": ""}, follow_redirects=False)   # borra solo el conjunto de jul/P1
with db.engine_owner.connect() as cn:
    resto = cn.execute(text(
        "SELECT cod_dane FROM macromedicion WHERE empresa_id=:e AND anio=2024 AND mes=7 AND punto='P1' "
        "ORDER BY cod_dane"), {"e": EID}).scalars().all()
check(set(resto) == {"41001", "41524"}, f"tras borrar el conjunto quedan Neiva y Palermo ({resto})")

# Limpieza: dejamos la macromedición como estaba (solo quitamos nuestros puntos de prueba).
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM macromedicion WHERE empresa_id=:e AND punto = ANY(:p)"),
               {"e": EID, "p": list(MIS)})

print("\n" + ("TODAS LAS PRUEBAS DE APS EN CARGUE PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
