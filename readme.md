## Proyecto: Plataforma de procesamiento de videos (FastAPI + Celery + Nginx)
### Imtegrantes 
- Alejandro Forero Gomez
- David Armando Rodríguez Varón
- Juan Sebastián Sánchez Tabares
- Yesid Arley Marin Rivera

### Entregas
- Semana 1: [Documento de la entrega](./docs/entregas/semana_1/semana_1.md)
- Semana 2: [Arquitectura ajustada (EC2 + NFS + RDS)](./docs/entregas/entrega_2/entrega_2.md)
- Semana 3: [Arquitectura ajustada (Auto Scaling + ALB + S3 + CloudWatch)](./docs/entregas/entrega_3/entrega_3.md)
- Semana 4: [Pruebas de carga y throughput (SQS + S3 + Worker)](./docs/entregas/entrega_4/pruebas_de_carga_entrega4.md)

## Documentación 
### 1) Estructura del proyecto y cómo funciona cada parte

```
proyecto-nube/
  app/
    api/
      routes/                # Rutas de la API (auth, videos, etc.)
    core/
      config.py              # Configuración vía variables de entorno
      database.py            # Sesiones SQLAlchemy y Base
      security.py            # Autenticación y JWT
      storage.py             # Almacenamiento local de archivos
      utils/video_utils.py   # Utilidades de ffmpeg para procesar video
    models/
      models.py              # Modelos SQLAlchemy (User, Video, Vote)
    schemas/
      *.py                   # Esquemas Pydantic para requests/responses
    celery_worker.py         # Worker Celery que procesa videos en background
    main.py                  # Aplicación FastAPI y registro de routers
    alembic/                 # Migraciones de base de datos
  assets/                    # Recursos (watermark, intro/outro)
  uploads/                   # Subidas originales (montado en contenedores)
  processed/                 # Videos procesados (expuestos por Nginx)
  nginx/nginx.conf           # Reverse proxy hacia la API + estáticos procesados
  docker-compose.yml         # Orquestación de servicios (DB, Redis, API, Nginx, Celery)
  Dockerfile                 # Imagen de la API
  prestart.sh                # Arranque de Uvicorn en desarrollo
  requirements.txt           # Dependencias Python
  tests/                     # Pruebas
```

- API (FastAPI): expone endpoints en `/api/*` para autenticación y gestión de videos. Usa SQLAlchemy para la DB y Pydantic para validaciones.
- Celery: procesa los videos en segundo plano (recorte, escalado, watermark, intro/outro) usando ffmpeg.
- Nginx: actúa como reverse proxy a la API y sirve los videos procesados desde `/processed/`.
- Redis: broker/backend de Celery.
- Postgres: base de datos.

Flujo simplificado:
1. El usuario sube un video (`POST /api/videos/upload`).
2. Se guarda el archivo en `uploads/` y se crea un registro `Video` (estado `uploaded`).
3. Se encola una tarea Celery que genera el video final en `processed/` y actualiza el estado a `done`.
4. El cliente consulta sus videos procesados (`GET /api/videos/user`).

### 2) Cómo inicializar

Requisitos locales: Docker y Docker Compose.

1. Crear archivo `.env` en la raíz con, por ejemplo:
```
DATABASE_URL=postgresql+psycopg2://app_user:app_password@postgres:5432/app_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=supersecret
TESTING=false
CELERY_EAGER=0
```
2. Construir e iniciar servicios:
```bash
docker compose up -d --build
```
3. (Si usas Alembic) Aplicar migraciones:
```bash
docker compose exec rest_api alembic upgrade head
```
4. Acceder a la API vía Nginx: `http://localhost:8080/docs`.

Credenciales y usuarios se crean vía `/api/auth/signup` y login en `/api/auth/login` (JWT).

### 3) Comandos útiles

- Construir y levantar todo:
```bash
docker compose up -d --build
```
- Ver logs de la API / Nginx / Worker:
```bash
docker compose logs -f rest_api
docker compose logs -f nginx
docker compose logs -f celery_worker
```
- Aplicar migraciones Alembic:
```bash
docker compose exec rest_api alembic revision -m "mensaje" --autogenerate
docker compose exec rest_api alembic upgrade head
```
- Ejecutar tests:
```bash
docker compose exec rest_api pytest -q
```

### 4) Errores comunes y soluciones

- Error al ejecutar `prestart.sh`: "exec format error"
  - Asegúrate de que `prestart.sh` tenga shebang `#!/bin/sh` y finales de línea LF. El `Dockerfile` limpia CRLF y aplica `chmod +x`.

- Respuesta 500 al listar videos por validación Pydantic
  - Ocurre si campos como `processed_path`/`uploaded_at` aún no existen. Los esquemas permiten `None` y el endpoint filtra `status=done`.

- URLs devuelven `http://localhost:8000`
  - Revisa Nginx: debe reenviar `Host`/`X-Forwarded-Host` y `X-Forwarded-Proto`. El backend construye URLs absolutas usando esos headers.

- ffmpeg no encontrado
  - La imagen de la API instala ffmpeg. Si falla, reconstruye: `docker compose build --no-cache rest_api`.

- Migraciones inconsistentes
  - Genera una nueva revisión con `alembic revision --autogenerate` y aplica `alembic upgrade head`.

### 5) Documentación

- La documentación  y las entregas se encontraran  seen la carpeta `docs/`.
- La especificación OpenAPI está disponible en `/docs` y `/openapi.json` a través de Nginx (`http://localhost:8080`).

### 6) Load Testing (Pruebas de Carga)

El proyecto incluye una infraestructura completa para pruebas de carga y análisis de capacidad.

#### Componentes de Monitoreo

El sistema incluye:
- **Prometheus** (`http://localhost:9090`): Recolección de métricas
- **Grafana** (`http://localhost:3001`): Visualización de métricas (admin/admin)
- **Locust**: Generación de carga para pruebas web
- **Script de inyección**: Para pruebas directas de workers

#### Inicio Rápido

1. **Levantar infraestructura con monitoreo:**
```bash
docker compose up -d
```

2. **Instalar herramientas de pruebas:**
```bash
cd load_tests
pip install -r requirements.txt
```

3. **Ejecutar prueba smoke (validación rápida):**
```bash
locust -f locustfile_web.py --users 5 --spawn-rate 5 --run-time 1m \
  --host http://localhost:8080 --headless
```

4. **Ver métricas en tiempo real:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (Dashboard: "FastAPI Load Testing Metrics").
  Si el dashboard no aparece, copia el archivo `grafana/dashboards/api_metrics.json` a la ruta `/var/lib/grafana/dashboards/` dentro del contenedor de Grafana y reinicia el servicio.

#### Escenarios de Prueba

**Escenario 1: Capacidad de Capa Web**
- Objetivo: Determinar usuarios concurrentes máximos
- Endpoint: `/api/videos/upload-mock` (sin procesamiento worker)
- SLOs: p95 ≤ 1s, errores ≤ 5%

```bash
locust -f locustfile_web.py --users 100 --spawn-rate 0.55 --run-time 8m \
  --host http://localhost:8080 --headless --html reports/ramp_100users.html
```

**Escenario 2: Throughput de Workers**
- Objetivo: Medir videos/min procesados
- Método: Inyección directa a cola Redis
- Variables: Tamaño de video (50MB, 100MB, 200MB) y concurrencia (1, 2, 4 workers)

```bash
python inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor
```

#### Documentación Completa

- **Guía de Load Testing**: [load_tests/README.md](load_tests/README.md)
- **Análisis de Capacidad**: [docs/entregas/entrega_1/analisis_capacidad.md](docs/entregas/entrega_1/analisis_capacidad.md)
- **Análisis de Capacidad (Entrega 3)**: [capacity-planning/pruebas_de_carga_entrega3.md](capacity-planning/pruebas_de_carga_entrega3.md)

#### Ajustar Concurrencia de Workers

Para pruebas de Escenario 2, modificar en `docker-compose.yml`:

```yaml
celery_worker:
  command: celery -A app.celery_worker.celery_app worker --loglevel=info --concurrency=4
```

Luego reiniciar:
```bash
docker compose restart celery_worker
```

### 7) Almacenamiento en S3 (Cloud)

Para entornos en la nube, habilita S3 como backend de almacenamiento (bucket privado con URLs prefirmadas):

1. Configura `.env`:

```
STORAGE_BACKEND=s3
AWS_REGION=us-east-1
AWS_S3_BUCKET=tu-bucket
S3_UPLOAD_PREFIX=uploads
S3_PROCESSED_PREFIX=processed
S3_URL_EXPIRE_SECONDS=3600

2. Flujo con S3:
   - La API sube el original a `s3://{bucket}/{S3_UPLOAD_PREFIX}/...`.
   - El worker descarga el original desde S3, procesa localmente y sube el final a `s3://{bucket}/{S3_PROCESSED_PREFIX}/...`.
   - El original en S3 se elimina tras el procesamiento exitoso.
   - Los endpoints devuelven URLs prefirmadas que expiran en `S3_URL_EXPIRE_SECONDS`.

