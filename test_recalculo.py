# -*- coding: utf-8 -*-
"""Pruebas del motor de recálculo mensual (seguimiento).

  · CCP del mes con tope IPUF* (art. 2.1.2.1.3.3): pérdidas reconocidas ≤ estándar;
  · el motor reproduce los componentes validados al alimentarlo con drivers = año base;
  · integración: recalcular por empresa produce costos del mes y acumulado, y la CCP
    muestra el castigo por pérdidas de la macromedición de muestra;
  · carga del balance del mes → numeradores clasificados (origen 'balance');
  · aislamiento: un usuario Empresa no puede recalcular/ver otra empresa.
"""
import re
from sqlalchemy import text
from starlette.testclient import TestClient
import config, main, db
import recalculo_service as rs

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


# ---------------- 1) Unidad: CCP con tope IPUF* ----------------
print("== CCP del mes con tope IPUF* (art. 2.1.2.1.3.3) ==")
# pérdidas reales (2.200.000-1.463.017=736.983) > estándar (6×122.188=733.128) → capado
ccp, pr, rec = rs.ccp_mes(af=1463017, ap=2200000, n=122188, ipuf=6)
check(abs(rec - 6 * 122188) < 1 and abs(ccp - (1463017 + 6 * 122188)) < 1,
      f"pérdidas capadas al estándar (reconocidas={rec:,.0f}, CCP={ccp:,.0f})")
# pérdidas reales < estándar → se reconoce toda la producción (CCP=AP)
ccp2, pr2, rec2 = rs.ccp_mes(af=1000000, ap=1050000, n=100000, ipuf=6)
check(abs(ccp2 - 1050000) < 1, f"pérdidas bajo el estándar: CCP=AP ({ccp2:,.0f})")
# sin macromedición (AP=0) → CCP=AF
ccp3, _, _ = rs.ccp_mes(af=500000, ap=0, n=50000, ipuf=6)
check(ccp3 == 500000, "sin AP: CCP = AF")

# ---------------- 2) Reproducción del año base ----------------
print("== Reproducción de los componentes validados (drivers = año base) ==")
with db.engine_owner.connect() as cn:
    OBJ = {(r["empresa_id"], r["servicio"], r["componente"]): float(r["valor"])
           for r in cn.execute(text("SELECT empresa_id,servicio,componente,valor FROM "
           "resultado_componente WHERE componente IN ('CMA','CMO')")).mappings().all()}
    base = {}
    for r in cn.execute(text("SELECT empresa_id,servicio,clave,valor FROM base_calculo")).mappings().all():
        base.setdefault((r["empresa_id"], r["servicio"]), {})[r["clave"]] = float(r["valor"])
reprod_ok = True
for (eid, serv), bs in base.items():
    kct = bs["kct"]
    n = bs["N"]; ccp = bs["CCP"] / 12.0
    num = {c: bs.get(c, 0.0) / 12.0 for c in rs.CONCEPTOS}
    cma, cmo, _ = rs._costos(num, kct, bs["Fa_cma"], bs["Fa_cmo"], bs["Fa_cmict"], n, ccp, ccp)
    for comp, val in (("CMA", cma), ("CMO", cmo)):
        obj = OBJ.get((eid, serv, comp))
        if obj and abs((val - obj) / obj) > 0.001:
            reprod_ok = False
            print(f"    dif {eid} {serv} {comp}: {val:.2f} vs {obj:.2f}")
check(reprod_ok, "CMA y CMO reproducen el estudio al 0,1% en las 3 empresas")

# ---------------- 3) Integración: recalcular (admin) ----------------
print("== Integración: recalcular Las Ceibas (admin) ==")
admin = cli("mgomeza78@gmail.com")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/recalculo")
r = admin.post(f"/empresa/{LAS_CEIBAS}/recalcular-mes", data={"csrf": tok}, follow_redirects=False)
check("procesado" in r.headers.get("location", ""), f"recálculo procesado ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    fila = cn.execute(text("SELECT ccp_mes, ap_mes, af_mes, ianc, cma_mes, cmo_mes, cmi_mes, cmict_mes "
        "FROM costo_referencia_mensual WHERE empresa_id=:e AND servicio='acueducto' AND mes=7"),
        {"e": LAS_CEIBAS}).mappings().first()
check(fila is not None, "hay fila de costo de referencia (acueducto, jul)")
if fila:
    check(fila["ccp_mes"] < fila["ap_mes"], f"castigo por pérdidas: CCP ({fila['ccp_mes']:,.0f}) < AP ({fila['ap_mes']:,.0f})")
    check(fila["ianc"] and fila["ianc"] > 30, f"IANC de la muestra ≈ {fila['ianc']:.1f}%")
    check(all(fila[k] is not None and fila[k] > 0 for k in ("cma_mes", "cmo_mes", "cmi_mes", "cmict_mes")),
          "CMA/CMO/CMI/CMICT del mes calculados")

# ---------------- 4) Carga del balance del mes → numeradores ----------------
print("== Carga del balance del mes (clasificación → numeradores 'balance') ==")
balance = ("CODIGO,NOMBRE,SALDO INICIAL,DEBITO,CREDITO,SALDO FINAL\n"
           "51010101,SUELDOS,0,0,0,1200000000\n"
           "75010401,INCAPACIDADES,0,0,0,900000000\n"
           "7502021702,ENERGIA,0,0,0,300000000\n"
           "75020295,IVA MAYOR VALOR COSTO,0,0,0,150000000\n"
           "75020807,TASA RRNN,0,0,0,80000000\n"
           "51111708,ALUMBRADO PUBLICO,0,0,0,50000000\n")
tok = csrf(admin, f"/empresa/{LAS_CEIBAS}/recalculo")
r = admin.post(f"/empresa/{LAS_CEIBAS}/cargar-balance",
               data={"anio": 2026, "mes": 7, "csrf": tok},
               files={"archivo": ("balance jul.csv", balance, "text/csv")}, follow_redirects=False)
check("clasificados" in r.headers.get("location", ""), f"balance clasificado y recálculo ({r.headers.get('location')})")
with db.engine_owner.connect() as cn:
    nbal = cn.execute(text("SELECT count(*) FROM numerador_mensual WHERE empresa_id=:e AND mes=7 "
                           "AND origen='balance'"), {"e": LAS_CEIBAS}).scalar_one()
    org = cn.execute(text("SELECT origen_numerador FROM costo_referencia_mensual WHERE empresa_id=:e "
                          "AND servicio='acueducto' AND mes=7"), {"e": LAS_CEIBAS}).scalar()
check(nbal > 0, f"numeradores del balance persistidos ({nbal} filas)")
check(org == "balance", f"el recálculo de jul usa el balance (origen={org})")

# ---------------- 5) Aislamiento ----------------
print("== Aislamiento: ESSMAR no ve ni recalcula Las Ceibas ==")
essmar = cli("operador@essmar.gov.co")
r = essmar.get(f"/empresa/{LAS_CEIBAS}/recalculo", follow_redirects=False)
check(r.status_code in (302, 303) and "no+disponible" in r.headers.get("location", "").lower()
      or "panel" in r.headers.get("location", ""),
      f"ESSMAR no accede al recálculo de Las Ceibas ({r.headers.get('location')})")
tok = csrf(essmar, f"/empresa/{ESSMAR}/recalculo")
r = essmar.post(f"/empresa/{LAS_CEIBAS}/recalcular-mes", data={"csrf": tok}, follow_redirects=False)
loc = r.headers.get("location", "")
check("no+disponible" in loc.lower() or "no+autorizado" in loc.lower() or "panel" in loc,
      f"ESSMAR no puede recalcular Las Ceibas ({loc})")

print("\n" + ("TODAS LAS PRUEBAS DE RECÁLCULO PASARON" if not _fail else f"FALLARON {len(_fail)}: {_fail}"))
raise SystemExit(1 if _fail else 0)
