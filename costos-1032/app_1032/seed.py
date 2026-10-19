# -*- coding: utf-8 -*-
"""Semilla de datos (se ejecuta como el rol dueño; bypassa RLS).

Crea el catálogo normativo, las tres empresas reales desde el núcleo, calcula sus
costos económicos de referencia con el núcleo validado, y crea los usuarios:
administrador (consultor), un analista, y un usuario Empresa por cada prestador.
"""
from sqlalchemy import text
from db import engine_owner
import config
import nucleo_service as ns
from security import hash_password

SEG = [
    # id, nombre, susc_min, susc_max, r, kct, ipuf*, art_r, art_kct
    (1, "Primer segmento (> 300.000 suscriptores)", 300001, None, 0.0858, 0.0178, 6.0,
     "2.1.2.1.3.1.7", "2.1.2.1.3.1.8"),
    (2, "Segundo segmento (90.000 – 300.000 suscriptores)", 90000, 300000, 0.0903, 0.0154, 6.0,
     "2.1.2.1.3.1.7", "2.1.2.1.3.1.8"),
]
ROLES = [(1, "admin", "Administrador"), (2, "analista", "Analista"),
         (3, "empresa", "Empresa"), (4, "auditor", "Auditor (solo lectura)")]

EMPRESAS = ["LAS_CEIBAS", "ESSMAR", "AMB"]

# usuarios Empresa (uno por prestador) + analista + auditor de muestra
USUARIOS_EMPRESA = {
    "LAS_CEIBAS": ("operador.neiva@lasceibas.gov.co", "Operador Las Ceibas"),
    "ESSMAR":     ("operador@essmar.gov.co", "Operador ESSMAR"),
    "AMB":        ("operador@amb.com.co", "Operador amb"),
}


def main():
    pw = hash_password(config.SEED_PASSWORD)
    with engine_owner.begin() as c:
        c.execute(text("TRUNCATE empresa, usuario, usuario_empresa, resultado_componente, "
                       "carga_mensual, auditoria, segmento, rol RESTART IDENTITY CASCADE"))
        for s in SEG:
            c.execute(text("INSERT INTO segmento(id,nombre,susc_min,susc_max,r,kct,ipuf_estrella,"
                           "articulo_r,articulo_kct) VALUES (:a,:b,:c,:d,:e,:f,:g,:h,:i)"),
                      dict(zip("abcdefghi", s)))
        for r in ROLES:
            c.execute(text("INSERT INTO rol(id,codigo,nombre) VALUES (:a,:b,:c)"),
                      dict(zip("abc", r)))

        emp_id = {}
        for code in EMPRESAS:
            b = ns.perfil_resumen(code)
            row = c.execute(text(
                "INSERT INTO empresa(codigo,nombre,municipio,segmento_id,presta_ac,presta_al,"
                " esquema,r,kct,fecha_inicio_688,fecha_inicio_1032,aplicacion_1032_tardia) "
                "VALUES (:codigo,:nombre,:municipio,:seg,:ac,:al,:esq,:r,:kct,:f688,:f1032,:tardia) "
                "RETURNING id"),
                {"codigo": b["codigo"], "nombre": b["nombre"], "municipio": b["municipio"],
                 "seg": b["segmento"], "ac": b["presta_ac"], "al": b["presta_al"],
                 "esq": b["esquema"], "r": b["r"], "kct": b["kct"],
                 "f688": b["fecha_inicio_688"], "f1032": b["fecha_inicio_1032"],
                 "tardia": b["aplicacion_1032_tardia"]}).scalar_one()
            emp_id[code] = row
            # costos económicos de referencia (núcleo validado)
            for f in ns.calcular(code):
                c.execute(text(
                    "INSERT INTO resultado_componente(empresa_id,servicio,componente,valor,"
                    " unidad,procedencia,fuente,articulo) VALUES (:e,:s,:cp,:v,:u,:p,:f,:a)"),
                    {"e": row, "s": f["servicio"], "cp": f["componente"], "v": f["valor"],
                     "u": f["unidad"], "p": f["procedencia"], "f": f["fuente"], "a": f["articulo"]})

        # administrador (consultor) — ve todas las empresas
        c.execute(text("INSERT INTO usuario(email,nombre,password_hash,rol_id,empresa_id) "
                       "VALUES (:em,:no,:ph,1,NULL)"),
                  {"em": "mgomeza78@gmail.com", "no": "Mauro Gómez (consultor)", "ph": pw})
        # analista interno — todas las empresas
        c.execute(text("INSERT INTO usuario(email,nombre,password_hash,rol_id,empresa_id) "
                       "VALUES (:em,:no,:ph,2,NULL)"),
                  {"em": "analista@sictaa.co", "no": "Analista SICTAA", "ph": pw})
        # un usuario Empresa por prestador — solo su empresa
        for code, (em, no) in USUARIOS_EMPRESA.items():
            c.execute(text("INSERT INTO usuario(email,nombre,password_hash,rol_id,empresa_id) "
                           "VALUES (:em,:no,:ph,3,:eid)"),
                      {"em": em, "no": no, "ph": pw, "eid": emp_id[code]})
        # auditor de muestra — solo lectura de Las Ceibas
        c.execute(text("INSERT INTO usuario(email,nombre,password_hash,rol_id,empresa_id) "
                       "VALUES (:em,:no,:ph,4,:eid)"),
                  {"em": "auditor@sspd.gov.co", "no": "Auditor (muestra)", "ph": pw,
                   "eid": emp_id["LAS_CEIBAS"]})

    # resumen
    with engine_owner.connect() as c:
        ne = c.execute(text("SELECT count(*) FROM empresa")).scalar_one()
        nr = c.execute(text("SELECT count(*) FROM resultado_componente")).scalar_one()
        nu = c.execute(text("SELECT count(*) FROM usuario")).scalar_one()
    print(f"Semilla lista: {ne} empresas, {nr} componentes calculados, {nu} usuarios.")
    print(f"Contraseña de todos los usuarios semilla: {config.SEED_PASSWORD}")


if __name__ == "__main__":
    main()
