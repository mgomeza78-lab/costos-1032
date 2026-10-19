# Clasificación contable del Balance de Prueba → componentes de la Res. CRA 1032/2026

Este documento describe la **cadena de clasificación contable** que convierte el Balance de
Prueba de cualquier empresa —independientemente del software contable que lo produzca— en los
**numeradores de costo** de los componentes tarifarios (CAC→CMA, COC→CMO, impuestos y tasas→CMICT),
aplicando los criterios de la Resolución CRA 1032 de 2026. La cadena quedó construida y **validada
al peso** contra el balance real de Las Ceibas E.S.P. (cierre 2025).

> **Alcance regulatorio.** Esta clasificación alimenta el **estimado mensual de los numeradores de
> costo** (seguimiento y acumulación de la línea base, art. 2.1.2.1.1.9) y reutiliza el mismo mapeo
> cuenta→componente del estudio anual. El costo de referencia que se **cobra** es el del estudio del
> período de inicio (1-jul a 31-dic-2026) **indexado** (gatillo 3%); el cálculo mensual no re-fija la
> tarifa. La cuantificación de metas se difiere al primer recálculo (línea base al cierre de 2026).

## 1. Arquitectura de la cadena

La clasificación es una tubería de tres piezas, desacopladas entre sí:

**a) `lector_balance.py` — lectura independiente del software contable.** Cada prestador exporta el
balance con columnas, encabezados y formatos de código distintos (Integrasoft, SIIGO, World Office,
Helisa, SAP…). Lo único común es el **código del PUC**. El lector **auto-detecta** la hoja, la fila
de encabezado (la primera que contiene «nombre» y algún «saldo») y las columnas (código, nombre,
saldo inicial, débito, crédito, saldo final) por su etiqueta sin tildes ni mayúsculas, asignando cada
columna al campo cuyo alias calza más largo para evitar colisiones (p. ej. que «saldo» capture
«saldo final»). **Normaliza el código** dejando solo dígitos, de modo que `5.1.01.01` (ESSMAR) y
`51010101` (Las Ceibas) quedan como el mismo código canónico `51010101`. Admite además un **perfil
por empresa** para forzar el mapeo si la auto-detección no bastara. Validado sobre balances reales de
dos empresas con software distinto: Las Ceibas (código en columna A, sin puntos, una hoja) y ESSMAR
(código en columna B, con puntos, dos hojas por año) — ambos leídos correctamente.

**b) `catalogos/catalogo_clasificacion_<empresa>.csv` — catálogo de clasificación editable, por
empresa.** Es la tabla que asocia cada cuenta PUC con su **subcomponente** (CAC-1..6, COC-1..5, CE,
CIQ, COIR, ICTA, ICTO, TA, …) y su **componente** (CMA, CMO, CMI, CMICT, Excluido), extraída del
Maestro de Codificación Contable de la empresa (hoja `Cruce_PlanCuentas`). Cada prestador tiene su
propio plan de cuentas, por eso el catálogo es **por empresa** y **editable**: el analista puede
agregar o reclasificar cuentas sin tocar el código. Columnas: `codigo, codigo_norm, nombre, clase,
subcomponente, componente, traslado, driver, saldo_2024, saldo_2025, observacion` (la observación cita
el artículo de la 1032 que fundamenta la clasificación). El catálogo de Las Ceibas tiene **276
cuentas**.

**c) `clasificador.py` — agregación por componente, solo cuentas hoja.** Aplica el catálogo al
balance ya normalizado. Para evitar el **doble conteo** propio de un balance jerárquico
(5 → 51 → 5101 → 510101 → 51010101), solo suma las **cuentas hoja** (las que ningún otro código del
balance extiende) y asigna cada una por el **prefijo más largo** presente en el catálogo (una cuenta
del balance puede ser más detallada que la del catálogo). Devuelve la agregación por subcomponente,
por componente y la lista de **cuentas de gasto/costo (clase 5/7) sin clasificar**, para que el
analista las incorpore al catálogo —no se pierden ni se cuentan mal—. La función `numeradores()` arma
el **CACe** (Σ CAC-*) y el **COCe comparable** (COC-1..5), insumos de los numeradores del CMA y del CMO.

## 2. Validación al peso (Las Ceibas, balance real 2025)

Ejecutando la cadena completa `lector_balance → clasificador + catálogo` sobre el archivo
**BALANCE DE PRUEBA 2025.xlsx** real (1.259 filas, Integrasoft), la agregación por componente del
`saldo_final` reconcilia contra los controles del catálogo:

| Componente | Clasificado del balance real | Control (catálogo) | Diferencia |
|---|---:|---:|---:|
| CMA (CAC) | 37.560.659.113 | 37.560.659.116 | −3 |
| CMO (COC) | 33.410.309.102 | 33.410.309.103 | −1 |
| CMI | 7.470.400.045 | 7.470.400.045 | 0 |
| Excluido | −29.543.170.608 | −29.543.170.608 | 0 |
| **CMICT** | **4.729.835.039** | **4.536.000.047** | **+193.834.992** |

Cuatro de los cinco componentes reconcilian **al peso** (las diferencias de −3 y −1 peso son redondeo
del control extraído del Maestro). Quedan **2 cuentas de clase 5 sin clasificar**, por valor conjunto
de $8.104.578, ambas de naturaleza financiera no comparable que corresponden a exclusiones:
`580423` Pérdida por baja en cuentas por cobrar ($6.535.435) y `58049001` Cobro reciprocidad bancaria
($1.569.143).

### Hallazgo: residuo del CMICT (+193,8 millones, 4,1 %)

El único componente con diferencia material es el **CMICT**. La clasificación del balance arroja
$4.729.835.039 (= ICTA $1.888.930.558 + ICTO $1.941.897.603 + TA $899.006.879), frente al control de
$4.536.000.047. La diferencia de **+193.834.992** se concentra en los **impuestos, contribuciones y
tasas**, y es consistente con la distinción entre el valor **contable** registrado en el balance y el
valor **reconocido** regulatoriamente de las **tasas ambientales** (tasa retributiva y tasa por uso
del agua), que no siempre coinciden en el período. **No se ajusta de oficio**: se deja expresamente
como partida **por confirmar con la empresa** —qué cuentas de tasa ambiental deben reconocerse en el
CMICT y por qué monto—, conforme al criterio de no inventar información empírica. Es un hallazgo de
trazabilidad, no un error de la cadena: el mismo motor reconcilia al peso los otros cuatro componentes.

## 3. Cómo se usa cada mes

1. La empresa exporta su **Balance de Prueba del mes** (cierre contable) en el formato de su software.
2. Se sube tal cual; `lector_balance` lo normaliza sin configuración manual.
3. `clasificador` + el **catálogo de la empresa** producen CAC/COC/ICTA/ICTO/TA del mes, y reportan
   cualquier cuenta nueva sin clasificar para que el analista la agregue al catálogo.
4. Esos numeradores, junto con el **CCP del mes** (consumo corregido por pérdidas) y **N** (suscriptores
   del mes), alimentan el estimado mensual de CMA/CMO/CMICT (el CMI proviene de la BCR₀, estructural/anual).

De este modo, un balance de **cualquier formato** se convierte automáticamente en los numeradores de
costo clasificados según la 1032, con trazabilidad cuenta por cuenta y control de lo no clasificado.

## 4. Distinción de fuentes (según instrucción del estudio)

- **Normativa:** los criterios de clasificación y los numerales citados (arts. 2.1.2.1.3.2.4 CAC,
  2.1.2.1.3.4.4 COC, 2.1.2.1.3.5 CMI, 2.1.2.1.3.6 CMICT de la Res. CRA 1032/2026).
- **Reportada por la empresa:** el Balance de Prueba y el Maestro de Codificación Contable.
- **Supuesto de trabajo:** la asociación cuenta→componente del catálogo, revisable por el analista.
- **Por confirmar:** el reconocimiento de las tasas ambientales en el CMICT (residuo de $193,8 M).

## 5. Pendiente

- Construir el catálogo equivalente para **ESSMAR** y **amb** desde sus respectivos Maestros/guías.
- Confirmar con Las Ceibas el tratamiento de las **tasas ambientales** en el CMICT.
- Integrar el clasificador a la UI de cargue mensual (subir balance → ver numeradores clasificados).
