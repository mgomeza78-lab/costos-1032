# Años tarifarios — marco temporal del cargue de información

Se fijó en el sistema, como **referencia canónica**, la estructura de años tarifarios de la
Res. CRA 1032/2026, para que toda la información que se cargue quede **atada a su año tarifario**
y el seguimiento, la indexación y los recálculos se atribuyan sin ambigüedad.

## Estructura (11 períodos de cargue)

| # | Año tarifario | Desde | Hasta | Meses | Rol |
|---|---|---|---|---|---|
| 0 | **Período de inicio** | 2026-07-01 | 2026-12-31 | 6 | Este estudio; el cálculo mensual es seguimiento/control. |
| 1 | Año tarifario 1 | 2027-01-01 | 2027-12-31 | 12 | Lo fija el **primer recálculo** (metas cuantificadas, línea base al cierre de 2026). |
| 2 | Año tarifario 2 | 2028-01-01 | 2028-12-31 | 12 | Recálculo / indexación. |
| … | … | … | … | 12 | … |
| 10 | Año tarifario 10 | 2036-01-01 | 2036-12-31 | 12 | Fin del horizonte del POIR. |

El **período de inicio NO es el año 1**: es previo (6 meses). El año tarifario 1 inicia el
1-ene-2027. En los cargues mensuales, el **año calendario determina el año tarifario**
(2026 → período de inicio; 2027 → año 1; …; 2036 → año 10).

## Qué quedó construido
- **`periodos.py`** — fuente canónica: la lista de los 11 períodos y los ayudantes
  `periodo_de(anio, mes)`, `etiqueta(anio, mes)`, `corto(...)`, `es_periodo_inicio(...)`. Nota: en
  2026 solo jul–dic pertenecen al período de inicio (ene–jun quedan fuera del horizonte).
- **`ano_tarifario`** (migración 008) — catálogo en la base (clave, etiqueta, año calendario,
  fechas, meses, es_inicio), común y de solo lectura, sembrado desde `periodos.py`.
- **UI**: página de referencia **«Años tarifarios»** en el menú; columna **«Año tar.»** en los
  tableros de operación mensual y de recálculo (muestra «Inicio», «Año 1», …), y el filtro de
  plantilla `anio_tar` / `anio_tar_full` disponible en cualquier vista.

## Para qué sirve
- **Cargue**: cada dato mensual (costos, volúmenes, suscriptores, avance del POIR) se ubica en su
  año tarifario; los años 1–10 se van abriendo a medida que transcurren.
- **Recálculos**: la acumulación de la línea base del período de inicio alimenta el **primer
  recálculo** (año 1); los recálculos/indexaciones posteriores corresponden a los años 2–10.
- **Consistencia**: evita confundir el período de inicio con el año 1 (un error frecuente), punto
  que la propia Res. 1032 distingue (período de inicio, art. 2.1.2.1.1.8; primer año tarifario desde 2027).
