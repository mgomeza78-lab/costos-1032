# Plataforma multiempresa — Estudios de costos CRA 1032/2026

Primer incremento de la aplicación: **fundación multiempresa + acceso**. Sobre el
núcleo de cálculo ya validado al peso (Las Ceibas, ESSMAR, amb), agrega la capa de
acceso y aislamiento que permite que el consultor vea todas las empresas y que cada
prestador vea **solo la suya**.

## Qué incluye este incremento

- **Autenticación** y sesión por cookie firmada; contraseñas con `bcrypt`.
- **Cuatro roles** con matriz de permisos: Administrador, Analista, Empresa, Auditor.
- **Aislamiento por empresa con Row-Level Security (RLS) de PostgreSQL**: el filtro por
  `empresa_id` lo impone la base, no la aplicación. La conexión de la app usa un rol
  (`app_user`) sin privilegio de *bypass* y que no es dueño de las tablas, de modo que
  las políticas RLS siempre aplican (defensa en profundidad).
- **Núcleo de cálculo conectado**: el recálculo de una empresa corre el núcleo validado
  (`nucleo/`) y guarda los costos económicos de referencia del período de inicio.
- **UI** mínima: ingreso, panel de empresas (según alcance), detalle con los costos por
  servicio y componente, alta de empresa, emisión de credenciales, matriz de permisos,
  bitácora de auditoría y «Mi cuenta» (cambio de contraseña + MFA).
- **Endurecimiento de seguridad**: cabeceras de seguridad, cookie de sesión endurecida con
  expiración, CSRF en todos los formularios, bloqueo por intentos, MFA (TOTP) opcional y
  política de contraseñas (ver sección «Endurecimiento de seguridad»).
- **Operación mensual**: carga mes a mes (suscriptores, m³, facturación, novedades; SUI o
  archivo propio), índice IPC mensual, **motor de indexación por gatillo del 3%** que
  produce la tarifa vigente, y tablero mensual por empresa (ver sección «Operación mensual»).

## Operación mensual (indexación por gatillo del 3%)

Bajo la Res. CRA 1032 (art. 2.1.2.1.5.3) y el art. 125 de la Ley 142 de 1994, los costos
económicos de referencia **no se recalculan cada mes**; lo que cambia es la **tarifa
vigente**, que se actualiza cuando la variación acumulada del IPC alcanza el **3%** desde
la última actualización. La capa implementa ese ciclo:

- **Carga mensual** (`carga_mensual`, con RLS): la Empresa alimenta suscriptores, m³
  facturados, facturación y novedades de su propia empresa (origen SUI o archivo propio).
- **Índice IPC** (`indice_ipc`): referencia nacional cargada (DANE); la mantienen
  Administrador/Analista en la pestaña «IPC». Es un **dato cargado, no inventado**.
- **Motor** (`operacion_service.py`): toma los cargos base del período de inicio
  (CARGO_FIJO y CARGO_CONSUMO ya validados) y, con el IPC mes a mes, acumula la variación;
  cuando alcanza el 3% aplica el factor y guarda la nueva tarifa vigente (`tarifa_vigente`),
  reiniciando la referencia del gatillo.
- **Tablero mensual** por empresa: serie jul–dic 2026 con IPC, variación acumulada vs. el
  gatillo, mes de indexación resaltado, cargo fijo y por consumo vigentes, y la carga del mes.

Los datos de IPC y de carga de la semilla (`seed_operacion.py`) son **ilustrativos**
(marcados «supuesto»/«muestra»); en operación real provienen del DANE y del SUI/archivo
de la empresa. El recálculo anual de fondo (art. 2.1.2.1.1.9) reusa la fábrica de
generadores con la línea base acumulada.

### Cargue mensual por CSV y factura por estrato

La operación se alimenta con **CSV separados** (ver `Definicion_cargues_mensuales.md` y las
plantillas), que se suben desde la plataforma:

- **Índices DANE** (`indices_dane.csv`): IPC e IPCs; se cargan en la pestaña «IPC»
  (Admin/Analista). La 1032 usa **dos canastas**: IPCs indexa CMA/CMO/CMICT, IPC indexa CMI,
  cada una con su propio gatillo del 3%.
- **Comercial** (`comercial_*.csv`, formulario SUI 6080/6081): suscriptores y consumos por
  **clase de uso** (estrato/uso), por servicio → tabla `carga_mensual_detalle` (RLS).
- **Factores de subsidio/contribución** (`factores_*.csv`, SUI 1051/1114) → `factor_subsidio`.
- **Indicadores** (`indicadores_*.csv`, SURICATA 6084) → `indicador_mensual`.

La **facturación no se carga: se deriva**. `operacion_service.derivar_factura` calcula, por
clase, la factura teórica = suscriptores × cargo fijo + consumo × cargo por consumo, aplicando
los factores de subsidio (−) y contribución (+) sobre el cargo fijo y el consumo básico; el
resultado va a `factura_clase` y se muestra como **factura por estrato** en el tablero mensual,
con el saldo subsidios⇄contribuciones (insumo del FSRI). La ingesta valida columnas y tipos,
y cada fila va en un SAVEPOINT (una fila inválida no tumba el resto); el `empresa_id` lo fija
la sesión, nunca el archivo (un CSV no puede escribir en otra empresa).

## Arquitectura

```
main.py            rutas FastAPI (login, panel, empresa, recalcular, usuarios, API JSON)
db.py              conexión + scope_conn(): fija app.allow_all / app.empresa_ids por petición
security.py        hash/verificación de contraseñas y utilidades de sesión
rbac.py            roles y matriz de permisos (qué puede hacer cada rol)
nucleo_service.py  puente al núcleo validado (perfil -> cálculo -> filas de resultado)
operacion_service.py  motor de indexación mensual por gatillo del 3% (tarifa vigente)
nucleo/            núcleo de cálculo validado (perfiles_empresa, bcr0_cmi, ... + CSV)
sql/001_schema.sql tablas (catálogo normativo, empresa, usuario, resultados, carga mensual…)
sql/002_rls.sql    rol de aplicación, políticas RLS y funciones SECURITY DEFINER de login
sql/003_hardening.sql  columnas de seguridad, autenticación ampliada, intentos y MFA
sql/004_operacion.sql  IPC mensual, carga ampliada y tarifa vigente (+ RLS)
seed.py / seed_operacion.py  catálogo + 3 empresas + usuarios; IPC + cargas ilustrativas
templates/ static/ vistas y estilos
```

**Cómo funciona el aislamiento.** Al iniciar sesión se resuelve el alcance del usuario
(`app_scope`): el Administrador y el Analista-sin-asignación obtienen `allow_all`; un
usuario Empresa/Auditor obtiene la lista con su único `empresa_id`. En cada petición,
`db.scope_conn` abre una transacción y fija ese contexto con `set_config(..., local)`.
Las políticas RLS de cada tabla comparan `empresa_id` contra ese contexto, así que
cualquier consulta queda filtrada aunque el código no incluya `WHERE empresa_id = …`.

## Requisitos

- Python 3.11+ y PostgreSQL 14+ (probado en 3.13 y PostgreSQL 16).
- `pip install -r requirements.txt`

## Puesta en marcha (Linux/Mac)

```bash
# 1) PostgreSQL en marcha y accesible (por defecto localhost:5433; ajústelo con
#    las variables DB_HOST/DB_PORT). Debe existir el rol dueño (p. ej. postgres).
pip install -r requirements.txt

# 2) Crea la BD, corre migraciones (esquema + RLS) y la semilla:
bash inicializar.sh

# 3) Arranca la aplicación:
bash correr.sh        # -> http://127.0.0.1:8000
```

## Puesta en marcha (Windows, PowerShell)

```powershell
pip install -r requirements.txt
# Con PostgreSQL instalado y en el PATH (ajuste puerto si no es 5433):
$env:PGPASSWORD="<clave de postgres>"
createdb -h localhost -p 5433 -U postgres estudios_1032
psql -h localhost -p 5433 -U postgres -d estudios_1032 -f sql\001_schema.sql
psql -h localhost -p 5433 -U postgres -d estudios_1032 -f sql\002_rls.sql
psql -h localhost -p 5433 -U postgres -d estudios_1032 -f sql\003_hardening.sql
psql -h localhost -p 5433 -U postgres -d estudios_1032 -f sql\004_operacion.sql
psql -h localhost -p 5433 -U postgres -d estudios_1032 -f sql\005_cargue.sql
python seed.py
python seed_operacion.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Credenciales de la semilla (demostración)

Contraseña de todos: **`Cambiar2026*`** (cámbiela; defínala con `SEED_PASSWORD`).

| Correo | Rol | Ve |
|---|---|---|
| `mgomeza78@gmail.com` | Administrador | las 3 empresas |
| `analista@sictaa.co` | Analista | las 3 empresas |
| `operador.neiva@lasceibas.gov.co` | Empresa | solo Las Ceibas |
| `operador@essmar.gov.co` | Empresa | solo ESSMAR |
| `operador@amb.com.co` | Empresa | solo amb |
| `auditor@sspd.gov.co` | Auditor | solo Las Ceibas (solo lectura) |

## Verificación del aislamiento

- `python test_aislamiento.py` — prueba end-to-end (login + sesión + rutas + RLS):
  el admin ve 3, la empresa ve 1, el acceso cruzado da 404, la empresa no puede
  recalcular, el admin sí.
- También a nivel de base, conectado como `app_user`, fijando `app.empresa_ids`: un
  usuario Empresa no lee ni **escribe** filas de otra (la política `WITH CHECK` rechaza
  el INSERT cruzado).

## Endurecimiento de seguridad (implementado)

- **Aislamiento por empresa con RLS** (última línea de defensa) + control por rol (primera).
- **Cabeceras de seguridad** en toda respuesta: `Content-Security-Policy` restrictiva,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, y `Strict-Transport-Security` en producción.
- **Cookie de sesión endurecida:** `HttpOnly`, `SameSite=Strict`, `Secure` en producción,
  con expiración (`SESSION_MAX_AGE`) y **regeneración de sesión** al iniciar (anti-fijación).
- **CSRF** en todos los formularios (token por sesión; se valida en cada POST).
- **Bloqueo por intentos fallidos:** tras `MAX_LOGIN_ATTEMPTS` (5) la cuenta se bloquea
  `LOCK_MINUTES` (15); mensajes genéricos (sin enumeración de usuarios); auditoría de
  login exitoso/fallido/bloqueado.
- **MFA (TOTP)** opcional por usuario (recomendado para Administrador/Analista):
  enrolamiento con QR en «Mi cuenta» y verificación de segundo factor en el ingreso.
- **Política de contraseñas** (longitud mínima + letra, número y símbolo) y **cambio de
  contraseña** de auto-servicio; las credenciales emitidas por el admin exigen cambio
  en el primer ingreso.
- **Secreto de sesión** obligatorio en producción (`APP_SECRET_KEY`); la app aborta si
  falta cuando `APP_ENV=prod`.
- **Funciones SECURITY DEFINER mínimas**: el auto-servicio (contraseña/MFA) solo afecta
  al usuario autenticado (atado a `app.user_id`), no recibe el id como parámetro.

### Variables de entorno de seguridad

`APP_ENV` (dev|prod) · `APP_SECRET_KEY` (obligatoria en prod) · `COOKIE_SECURE` ·
`SESSION_MAX_AGE` · `MAX_LOGIN_ATTEMPTS` · `LOCK_MINUTES` · `PASSWORD_MIN_LEN` ·
`DB_APP_PASSWORD` / `DB_OWNER_PASSWORD` · `MFA_ISSUER`.

### Pendiente a nivel de infraestructura (no de código)

- Terminación **HTTPS** (TLS) ante la app; poner `APP_ENV=prod` y `COOKIE_SECURE=1`.
- Contraseña real del rol `app_user` (`ALTER ROLE app_user WITH PASSWORD …`) y
  `pg_hba.conf` en `scram-sha-256` en vez de `trust`.
- Copia de seguridad y **cifrado en reposo** de la base; rotación periódica de secretos.

## Qué sigue (capa de operación mensual)

Esta fundación es la base de la operación mes a mes: alta de empresa guiada, carga
mensual (SUI/archivo propio) sobre la tabla `carga_mensual` (ya existe, con RLS), motor
de indexación por gatillo del 3% (faep₀) y tableros mensuales, más la orquestación del
recálculo anual del art. 2.1.2.1.1.9.
