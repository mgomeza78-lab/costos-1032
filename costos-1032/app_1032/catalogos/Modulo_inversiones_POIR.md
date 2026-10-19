# Módulo de Inversiones / POIR — registro y seguimiento

Cuarta pieza de la plataforma. Permite **crear proyectos de inversión** con los campos de la
Resolución CRA 1032 y **hacer seguimiento del avance físico y financiero** por corte, hasta la
entrada en operación. Cada proyecto se **clasifica** según el reconocimiento tarifario. Construido
en modo *registro + seguimiento* (acordado para el período de inicio) y probado automáticamente.

> **Alcance.** En el período de inicio (1-jul a 31-dic-2026) el módulo **solo registra y hace
> seguimiento**: no cuantifica el aporte al CMI_POIR, que **opera desde el primer año tarifario
> (2027), art. 2.1.2.1.3.5.14**. La base acumulada alimenta el **primer recálculo** y la
> **verificación del 80 %** de ejecución del POIR para que los activos entren a la BCR₀.

## Qué quedó construido

**Esquema (migración 007, con RLS por empresa):**
- `proyecto_inversion` — se crea **planeado**, con: código POIR, nombre, servicio (ac/al), APS,
  componente del sistema (captación, aducción, conducción, tratamiento, almacenamiento,
  distribución; recolección, transporte, tratamiento de aguas residuales), meta asociada,
  **clasificación** (`CMI_POIR` | `expost_general`), origen (`POIR_688` | `POIR_nuevo`),
  **valor planeado** (presupuesto), **fecha planeada de operación**, fecha real de operación,
  estado (planeado/en ejecución/en operación/suspendido), y —cuando aplica— **VIA688**, VP del
  recaudo y vida útil.
- `avance_inversion` — por corte (año/mes): **avance físico (%)** y **avance financiero
  ($ ejecutado acumulado)**, con observación.

**Servicio (`inversiones_service.py`):**
- `crear_proyecto` (upsert por código POIR, valida servicio y clasificación).
- `registrar_avance` (upsert del corte y **transición de estado**: pasa a *en ejecución* con el
  primer avance y a *en operación* cuando el avance físico llega al 100 % o se registra la fecha
  real de operación).
- `tablero` (proyectos con su último corte y el % de ejecución financiera).
- `resumen` (totales por **clasificación** y por **estado**, % de ejecución global, y el
  **chequeo del 80 %** por servicio para la entrada a la BCR₀).

**UI (`inversiones.html`, ruta `/empresa/{id}/inversiones`):** tarjetas de resumen (proyectos,
planeado, ejecutado, ejecución global), tabla de **ejecución por servicio con el umbral del 80 %**,
tabla de proyectos con estado y % de avance, y formularios para **crear/actualizar proyecto** y
**registrar el avance de un corte**.

## Las dos clasificaciones (lo que pediste)
- **Asociado al CMI_POIR** (`CMI_POIR`): activos del plan de obras e inversiones regulado que, una
  vez verificado el 80 % de ejecución, integran la base y se remuneran vía CMI desde 2027
  (art. 2.1.2.1.3.5.14).
- **Reconocimiento expost** (`expost_general`): se reconoce con la **fórmula general** del CMI
  (art. 2.1.2.1.3.5) una vez ejecutado y en operación, sin el tratamiento específico del POIR.

## Verificación (probado automáticamente)
`test_inversiones.py`, en verde (y las cinco suites previas siguen pasando):
- crear proyecto con los campos de la 1032; estado inicial *planeado*;
- registrar avance → *en ejecución*; avance 100 % + fecha real → *en operación*;
- resumen por servicio y % de ejecución (umbral 80 %);
- clasificación inválida rechazada;
- **aislamiento**: un usuario Empresa no crea ni ve proyectos de otra empresa (RLS).

## Cómo se usa
1. Se **crea el proyecto planeado** (presupuesto y fecha planeada de operación) y se elige su
   clasificación (CMI_POIR o expost).
2. A lo largo del año se **registra el avance** por corte (físico % y financiero $ acumulado).
3. Al entrar en operación se registra la **fecha real**; el estado pasa a *en operación*.
4. El **resumen** muestra el % de ejecución por servicio y si supera el **80 %** (insumo de la
   BCR₀ y del primer recálculo).

## Pendiente / siguiente
- Cuantificación del **CMI_POIR** de los proyectos clasificados (anualidad del VPI) para simular 2027.
- Carga masiva por CSV de proyectos y avances (hoy por formulario).
- Vínculo del avance del POIR con la verificación del 80 % que alimenta la BCR₀ del recálculo anual.
