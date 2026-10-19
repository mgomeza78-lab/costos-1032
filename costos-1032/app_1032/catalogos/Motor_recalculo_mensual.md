# Motor de recálculo mensual — costos de referencia del mes y acumulados

Tercera pieza de la capa mensual (tras la indexación por gatillo y la factura por estrato). Calcula
los **costos económicos de referencia del mes y acumulados** con los **drivers reales** (suscriptores,
consumo corregido por pérdidas y numeradores del balance clasificado), para **seguimiento/control**
y para **acumular la línea base** del recálculo anual (art. 2.1.2.1.1.9). Validado al peso contra el
estudio y probado automáticamente.

> **Aclaración regulatoria.** El motor **no re-fija la tarifa cobrada** —esa es el costo del estudio
> del período de inicio **indexado** por el gatillo del 3 % (`operacion_service`)—. El recálculo mensual
> es de control: monitorea CCP, pérdidas y suficiencia, y compara el costo de referencia del mes contra
> el cobrado. La cuantificación de metas sigue diferida al primer recálculo.

## Qué quedó construido

**Esquema (migración 006, todo con RLS por empresa):**
- `base_calculo` — parámetros y numeradores **base** por empresa/servicio (CACe, COCe, CE, CIQ, COIR,
  ICTA, ITO, TA, N, CCP, AF, denom_cmict, Fa_cma, Fa_cmo, Fa_cmict, kct, CMI_base), sembrados desde el
  núcleo validado.
- `macromedicion` — agua producida/suministrada por **punto**, mensual (cargue propio; agua en bloque
  del SUI ACU-C-1002/1003).
- `numerador_mensual` — numeradores de costo **del mes** que produce el clasificador sobre el balance.
- `costo_referencia_mensual` — resultados del mes y acumulados por empresa/servicio.

**Motor (`recalculo_service.py`):**
- **CCP del mes** (art. 2.1.2.1.3.3): `CCP = AF + pérdidas reconocidas`, con las pérdidas limitadas al
  estándar **IPUF\*** del segmento (m³/suscriptor·mes). Si las pérdidas reales ≤ estándar, se reconoce
  toda la producción (CCP = AP); si las superan, se reconoce solo hasta el estándar (**castigo por
  pérdidas**). Devuelve también el IANC.
- **Costos del mes y acumulado**, con las mismas fórmulas validadas del estudio aplicadas a los drivers
  del mes:
  - `CMA = CACe × (1+kct) / N × Fa_cma` (art. 2.1.2.1.3.2.1)
  - `CMO = (COCe+CE+CIQ+COIR) × (1+kct) / CCP × Fa_cmo` (art. 2.1.2.1.3.4.1)
  - `CMICT = (ICTA+ITO+TA) × (1+kct) / denom × Fa_cmict` (art. 2.1.2.1.3.6.1; denom = CCP en acueducto,
    AF en alcantarillado, escalado por el consumo del período)
  - `CMI` = estructural (BCR₀ anual); se reporta el valor base.
  - Acumulado = Σ numeradores / Σ drivers (year-to-date).
- **Suficiencia**: compara el costo de referencia del mes (cargo fijo = CMA; cargo consumo =
  CMO+CMI+CMICT) contra el **cobrado** (indexado) y reporta la brecha.
- **Numeradores del mes**: del **balance clasificado** si se cargó (origen `balance`), o por
  **prorrateo** del año base (/12) mientras no haya balance (origen `prorrateo_base`).
- **Reparto por servicio** (`split_servicio`): el balance llega por el total de la empresa; se reparte
  entre acueducto y alcantarillado según la participación de los numeradores base.

**Ingesta (`ingesta.py`):** `cargar_macromedicion` (CSV por punto) y `persistir_numeradores_mensual`
(del clasificador). La carga del balance del mes se hace por la UI: sube el balance (cualquier formato)
→ `lector_balance` + `clasificador` + catálogo → numeradores → recálculo.

**UI (`recalculo.html`, ruta `/empresa/{id}/recalculo`):** tablero por servicio con el costo de
referencia del mes (N, AF, AP, IANC, CCP, CMA/CMO/CMI/CMICT), el acumulado y la **brecha de suficiencia**
con semáforo; formularios para cargar el balance del mes y la macromedición.

## Verificación (probado automáticamente)

`test_recalculo.py`, en verde (y las suites de aislamiento, seguridad, operación y cargue siguen pasando):
- **CCP con tope IPUF\***: pérdidas capadas al estándar; si están por debajo, CCP = AP; sin producción, CCP = AF.
- **Reproducción**: alimentando el motor con drivers = año base, **CMA y CMO reproducen el estudio al
  0,1 %** en las tres empresas (Las Ceibas, ESSMAR, amb). El CMICT también reproduce, salvo amb, donde el
  motor da el valor **limpio** (−0,13 %): la diferencia es exactamente el doble conteo del impuesto de
  vehículos detectado en el análisis de mejoras.
- **Integración**: recalcular produce costos del mes y acumulado; la macromedición de muestra muestra el
  castigo por pérdidas (CCP < AP, IANC ≈ 33,5 %).
- **Balance del mes**: subir el balance clasifica y persiste los numeradores (origen `balance`) y el
  recálculo los usa.
- **Aislamiento**: un usuario Empresa no ve ni recalcula otra empresa (RLS).

## Qué cambia mes a mes vs. qué es estructural
Cambian **N** (suscriptores), el **CCP** (facturación + macromedición) y los **numeradores de costo**
(CAC/COC/ICT del balance). Son estructurales/normativos **r, kct, IPUF\*, Fa** y la **BCR₀** (CMI), que
vienen del estudio/año base.

## Pendiente
- Catálogos de clasificación de ESSMAR y amb (hoy solo Las Ceibas tiene catálogo; el motor ya es
  genérico y los toma por código de empresa).
- Módulo de **Inversiones/POIR**: crear proyectos con los campos de la Res. 1032, registrar avance
  físico y financiero hasta la entrada en operación, y clasificar cada proyecto como asociado al
  **CMI_POIR** o a reconocer **expost** con la fórmula general.
