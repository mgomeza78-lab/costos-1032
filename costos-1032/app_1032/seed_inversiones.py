# -*- coding: utf-8 -*-
"""Semilla de muestra del módulo de Inversiones/POIR (Las Ceibas). Ilustrativa:
proyectos con los campos de la 1032 y avances de un par de cortes. Rol dueño (bypassa RLS)."""
import os
from sqlalchemy import text
from db import engine_owner
import inversiones_service as inv

os.environ.setdefault("DB_HOST", "localhost"); os.environ.setdefault("DB_PORT", "5433")

# codigo, nombre, servicio, aps, componente, meta, clasificacion, origen, valor_planeado,
# fecha_planeada, via688, vp_recaudo, vida_util, [(mes, fisico, financiero, fecha_real)]
PROY = [
    ("POIR-AC-001", "Ampliación PTAP El Jardín", "acueducto", "Neiva", "tratamiento",
     "continuidad y calidad (IRCA)", "CMI_POIR", "POIR_688", 15000000000, "2026-11-30",
     9800000000, 7200000000, 25, [(7, 60, 9000000000, None), (9, 85, 12750000000, None)]),
    ("POIR-AC-002", "Renovación de redes de distribución Comuna 6", "acueducto", "Neiva",
     "distribución", "reducción de pérdidas (IANC)", "CMI_POIR", "POIR_nuevo", 8000000000,
     "2026-12-31", None, None, 30, [(7, 25, 2000000000, None), (9, 45, 3600000000, None)]),
    ("POIR-AL-001", "Reposición colector principal", "alcantarillado", "Neiva", "recolección",
     "cobertura de alcantarillado", "expost_general", "POIR_nuevo", 5000000000, "2026-10-31",
     None, None, 40, [(7, 70, 3500000000, None), (9, 100, 5000000000, "2026-09-20")]),
    ("POIR-AC-003", "Macromedición y sectorización (DMA)", "acueducto", "Neiva", "macromedición",
     "reducción de pérdidas (IANC)", "expost_general", "POIR_nuevo", 1200000000, "2026-12-15",
     None, None, 15, [(7, 40, 480000000, None)]),
]


def main():
    with engine_owner.begin() as c:
        eid = c.execute(text("SELECT id FROM empresa WHERE codigo='LAS_CEIBAS'")).scalar()
        if not eid:
            print("Las Ceibas no existe; omito."); return
        c.execute(text("DELETE FROM avance_inversion WHERE empresa_id=:e"), {"e": eid})
        c.execute(text("DELETE FROM proyecto_inversion WHERE empresa_id=:e"), {"e": eid})
        n = 0
        for (cod, nom, serv, aps, comp, meta, cl, org, vp, fpo, via, vpr, vu, avs) in PROY:
            pid, err = inv.crear_proyecto(c, eid, {
                "codigo_poir": cod, "nombre": nom, "servicio": serv, "aps": aps,
                "componente_sistema": comp, "meta_asociada": meta, "clasificacion": cl,
                "origen": org, "valor_planeado": vp, "fecha_planeada_operacion": fpo,
                "via688": via, "vp_recaudo": vpr, "vida_util": vu, "creado_por": None})
            if err:
                print(f"  {cod}: {err}"); continue
            for (mes, fis, fin, fr) in avs:
                inv.registrar_avance(c, eid, pid, 2026, mes, fis, fin, None, fr, None)
            n += 1
        print(f"Inversiones/POIR: {n} proyectos de muestra sembrados en Las Ceibas.")


if __name__ == "__main__":
    main()
