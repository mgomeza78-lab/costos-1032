# -*- coding: utf-8 -*-
"""Pruebas de Configuración del APS (art. 2.1.2.1.1.5 de la Res. CRA 1032).

  · la vista responde 200 y lista los municipios del prestador;
  · guardar el APS de un municipio persiste todos los criterios;
  · la validación de completitud y la condición especial se derivan bien;
  · no se puede configurar un APS de un municipio ajeno al prestador;
  · soportes: subida (formatos permitidos), descarga, rechazo de formato y borrado;
  · RLS/roles: un operador de otra empresa no ve ni modifica este APS;
  · un operador de la propia empresa sí puede configurar su APS.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import aps_service as aps

PW = config.SEED_PASSWORD
EID = 1            # Las Ceibas
NEIVA = "41001"
PALERMO = "41524"
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


# limpieza idempotente
with db.engine_owner.begin() as cn:
    cn.execute(text("DELETE FROM aps WHERE empresa_id=:e"), {"e": EID})

adm = cli("mgomeza78@gmail.com")

print("== La vista de APS responde y lista los municipios ==")
r = adm.get(f"/empresa/{EID}/aps")
check(r.status_code == 200, f"/empresa/{EID}/aps responde 200 ({r.status_code})")
check("Configuración del APS" in r.text, "muestra el título de configuración del APS")
check("Neiva" in r.text and "Palermo" in r.text, "lista los municipios atendidos (Neiva y Palermo)")
check("2.1.2.1.1.5" in r.text, "cita el art. 2.1.2.1.1.5")

print("== Guardar el APS de Neiva con la información mínima completa ==")
tok = csrf(adm, f"/empresa/{EID}/aps?mun={NEIVA}")
r = adm.post(f"/empresa/{EID}/aps/guardar", data={
    "csrf": tok, "cod_dane": NEIVA, "numero_aps": "1", "nombre": "APS Neiva",
    "servicios": "ambos", "zona": "urbana_rural", "sistema_rural": "integrado",
    "georref_presentada": "on", "georref_sistema": "MAGNA-SIRGAS",
    "instrumento_ot": "POT", "instrumento_ot_acto": "Acuerdo 026 de 2009",
    "reportado_municipio": "on", "pmaa": "on"}, follow_redirects=False)
check("msg=APS+guardada" in r.headers.get("location", ""), f"guardado OK ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT * FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                     {"e": EID, "c": NEIVA}).mappings().first()
check(row is not None, "el APS de Neiva quedó registrado")
if row:
    check(row["servicios"] == "ambos" and row["zona"] == "urbana_rural"
          and row["sistema_rural"] == "integrado", "servicios/zona/sistema rural guardados")
    check(row["georref_presentada"] and row["reportado_municipio"] and row["instrumento_ot"] == "POT",
          "georreferenciación, reporte e instrumento OT guardados")
    check(row["numero_aps"] == 1 and row["nombre"] == "APS Neiva", "número y nombre del APS guardados")
    check(aps.validaciones(dict(row)) == [], f"sin faltantes: APS completo ({aps.validaciones(dict(row))})")

print("== Condición especial derivada (Palermo: ZRNI + menor tamaño + PDET) ==")
tok = csrf(adm, f"/empresa/{EID}/aps?mun={PALERMO}")
adm.post(f"/empresa/{EID}/aps/guardar", data={
    "csrf": tok, "cod_dane": PALERMO, "servicios": "ac", "zona": "urbana_rural",
    "sistema_rural": "no_integrado_urbana", "ed_rural_zrni": "on", "menor_5000": "on",
    "pdet": "on"}, follow_redirects=False)
with db.engine_owner.connect() as cn:
    row = cn.execute(text("SELECT * FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                     {"e": EID, "c": PALERMO}).mappings().first()
ce = aps.condicion_especial(dict(row)) if row else []
check(any("ZRNI" in x for x in ce), f"detecta ZRNI ({ce})")
check(any("menor tamaño" in x for x in ce), "detecta APS de menor tamaño/PDET")

print("== No se puede configurar un APS de un municipio ajeno al prestador ==")
tok = csrf(adm, f"/empresa/{EID}/aps?mun={NEIVA}")
r = adm.post(f"/empresa/{EID}/aps/guardar", data={
    "csrf": tok, "cod_dane": "05001", "servicios": "ambos"}, follow_redirects=False)
check("err=" in r.headers.get("location", ""), "rechaza municipio ajeno (Medellín 05001)")
with db.engine_owner.connect() as cn:
    n = cn.execute(text("SELECT count(*) FROM aps WHERE empresa_id=:e AND cod_dane='05001'"),
                   {"e": EID}).scalar_one()
check(n == 0, "no creó el APS del municipio ajeno")

print("== Soportes: subida, descarga, rechazo de formato y borrado ==")
tok = csrf(adm, f"/empresa/{EID}/aps?mun={NEIVA}")
contenido = b"x,y\n1,2\n3,4\n"
r = adm.post(f"/empresa/{EID}/aps/archivo",
             data={"csrf": tok, "cod_dane": NEIVA, "categoria": "georreferenciacion"},
             files={"archivo": ("coordenadas.csv", contenido, "text/csv")},
             follow_redirects=False)
check("msg=Soporte+cargado" in r.headers.get("location", ""), "soporte CSV cargado")
with db.engine_owner.connect() as cn:
    arow = cn.execute(text("SELECT a.id, a.nombre, a.categoria, a.tamano FROM aps_archivo a "
                           "JOIN aps p ON p.id=a.aps_id WHERE p.empresa_id=:e AND p.cod_dane=:c"),
                      {"e": EID, "c": NEIVA}).mappings().first()
check(arow is not None and arow["nombre"] == "coordenadas.csv", "el soporte quedó asociado al APS")
if arow:
    dr = adm.get(f"/empresa/{EID}/aps/archivo/{arow['id']}")
    check(dr.status_code == 200 and dr.content == contenido, "la descarga devuelve el contenido exacto")
# rechazo de formato
r = adm.post(f"/empresa/{EID}/aps/archivo",
             data={"csrf": tok, "cod_dane": NEIVA, "categoria": "soporte_general"},
             files={"archivo": ("malware.exe", b"MZ...", "application/octet-stream")},
             follow_redirects=False)
check("err=Formato+no+admitido" in r.headers.get("location", ""), "rechaza formato .exe")
# borrado
if arow:
    r = adm.post(f"/empresa/{EID}/aps/archivo/{arow['id']}/eliminar",
                 data={"csrf": tok, "cod_dane": NEIVA}, follow_redirects=False)
    with db.engine_owner.connect() as cn:
        n = cn.execute(text("SELECT count(*) FROM aps_archivo WHERE id=:i"), {"i": arow["id"]}).scalar_one()
    check(n == 0, "el soporte se eliminó")

print("== RLS: un operador de otra empresa (AMB) no ve ni modifica este APS ==")
amb = cli("operador@amb.com.co")
r = amb.get(f"/empresa/{EID}/aps", follow_redirects=False)
check(r.status_code in (302, 303), "operador AMB es redirigido fuera del APS de Las Ceibas")
tokx = csrf(amb, "/panel")
r = amb.post(f"/empresa/{EID}/aps/guardar", data={
    "csrf": tokx, "cod_dane": NEIVA, "nombre": "HACKEADO", "servicios": "al"},
    follow_redirects=False)
with db.engine_owner.connect() as cn:
    nombre = cn.execute(text("SELECT nombre FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                        {"e": EID, "c": NEIVA}).scalar()
check(nombre == "APS Neiva", f"el APS de Neiva no fue alterado por AMB ({nombre})")

print("== El operador de la propia empresa sí puede configurar su APS ==")
op = cli("operador.neiva@lasceibas.gov.co")
tok = csrf(op, f"/empresa/{EID}/aps?mun={NEIVA}")
r = op.post(f"/empresa/{EID}/aps/guardar", data={
    "csrf": tok, "cod_dane": NEIVA, "nombre": "APS Neiva", "servicios": "ambos",
    "zona": "urbana_rural", "sistema_rural": "integrado", "georref_presentada": "on",
    "instrumento_ot": "POT", "reportado_municipio": "on", "observacion": "editado por el operador"},
    follow_redirects=False)
check("msg=APS+guardada" in r.headers.get("location", ""), "el operador de Las Ceibas guarda su APS")
with db.engine_owner.connect() as cn:
    obs = cn.execute(text("SELECT observacion FROM aps WHERE empresa_id=:e AND cod_dane=:c"),
                     {"e": EID, "c": NEIVA}).scalar()
check(obs == "editado por el operador", "la edición del operador quedó registrada")

print("\n" + ("TODAS LAS PRUEBAS DE APS PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
