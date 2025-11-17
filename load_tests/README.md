# Infraestructura de Pruebas de Carga

Este directorio contiene scripts y utilidades para pruebas de carga, útiles para medir la capacidad de la plataforma de procesamiento de videos.

## Resumen

Se evalúan dos escenarios principales:

1. **Escenario 1: Capacidad de la Capa Web** - Evalúa cuántos usuarios concurrentes puede manejar la API
2. **Escenario 2: Rendimiento del Worker** - Mide la capacidad de procesamiento de videos/minuto

## Prerrequisitos

### Instalación

```bash
cd load_tests
pip install -r requirements.txt
```

### Infraestructura

Asegúrate de que todo el stack de la aplicación esté arriba con monitoreo:

```bash
# Desde la raíz del proyecto
docker compose up -d

```

Esto levanta:
- FastAPI (puerto 8000, accedido vía Nginx en 8080)
- Celery Worker
- Redis
- PostgreSQL
- **Prometheus** (puerto 9090)
- **Grafana** (puerto 3001, usuario: admin, contraseña: admin)

## Escenario 1: Capacidad de la Capa Web

### Objetivo
Determinar el máximo de usuarios concurrentes que el endpoint `/api/videos/upload-mock` puede soportar cumpliendo los SLOs:
- Latencia p95 ≤ 1.0s
- Error rate ≤ 5%

### Tipos de prueba

#### 1. Smoke Test (Chequeo Inicial)
Verifica funcionalidad básica antes de realizar pruebas extensas:

```bash
locust -f locustfile_web.py \
  --users 5 \
  --spawn-rate 5 \
  --run-time 1m \
  --host http://localhost:8080 \
  --headless
```

#### 2. Ramp Test (Búsqueda de Capacidad)
Aumenta la carga gradualmente para encontrar el punto de quiebre:

```bash
# Prueba con 100 usuarios
locust -f locustfile_web.py \
  --users 100 \
  --spawn-rate 0.55 \
  --run-time 8m \
  --host http://localhost:8080 \
  --headless \
  --html reports/ramp_100users.html


#### 3. Sustained Test (Estabilidad Confirmada)
Ejecuta la prueba al 80% de la capacidad máxima para confirmar estabilidad:

```bash
# Si la capacidad máxima es 100 usuarios, probar con 80
locust -f locustfile_web.py \
  --users 80 \
  --spawn-rate 80 \
  --run-time 5m \
  --host http://localhost:8080 \
  --headless \
  --html reports/sustained_80users.html
```

#### 4. Modo Interactivo (Recomendado)
Utiliza la interfaz web para monitoreo en tiempo real:

```bash
locust -f locustfile_web.py --host http://localhost:8080
```

Luego abre http://localhost:8089 y configura los parámetros de la prueba.

### Monitoreo Durante las Pruebas

**Consultas de Prometheus** (http://localhost:9090):
```promql
# Tasa de peticiones
rate(http_requests_total[1m])

# Latencia p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[1m]))

# Porcentaje de error
rate(http_requests_total{status=~"4..|5.."}[1m]) / rate(http_requests_total[1m])
```

**Dashboard de Grafana** (http://localhost:3001):
- Usuario: admin/admin
- Navegar a dashboard "FastAPI Load Testing Metrics"

### Salidas Esperadas

- RPS (requests por segundo) al máximo rendimiento
- Distribución de latencias (p50, p95, p99)
- Porcentaje de error
- Identificación de cuellos de botella (CPU, memoria, disco)

## Escenario 2: Rendimiento del Worker

### Objetivo
Medir cuántos videos/minuto puede procesar la capa de worker en distintos niveles de concurrencia y tamaños de archivo.

### Matriz de Pruebas

Combinaciones a evaluar:
- **Tamaños de video:** 50MB, 100MB, 200MB
- **Concurrencia:** 1, 2, 4 workers (ajustable en `docker-compose.yml`)

### Ajustar Concurrencia del Worker

Edita `docker-compose.yml`:

```yaml
celery_worker:
  command: celery -A app.celery_worker.celery_app worker --loglevel=info --concurrency=4
```

Reinicia el worker:
```bash
docker compose restart celery_worker
```

### Tipos de Prueba

#### 1. Burst Test (Detectar Saturación)
Inyectar todas las tareas de una vez para encontrar el punto de saturación:

```bash
# Videos de 50MB
python inject_worker_tasks.py \
  --count 100 \
  --size 50MB \
  --mode burst \
  --monitor

# Videos de 100MB
python inject_worker_tasks.py \
  --count 50 \
  --size 100MB \
  --mode burst \
  --monitor

# Videos de 200MB
python inject_worker_tasks.py \
  --count 25 \
  --size 200MB \
  --mode burst \
  --monitor
```

#### 2. Sustained Test (Confirmar Throughput)
Inyectar tareas a una tasa controlada:

```bash
# 10 tareas/min por 5 minutos
python inject_worker_tasks.py \
  --count 50 \
  --size 100MB \
  --mode sustained \
  --rate 10 \
  --monitor
```

### Monitoreo del Worker

**Verificar longitud de cola (SQS)**:
```bash
QUEUE_URL=$(aws sqs get-queue-url --queue-name "$SQS_QUEUE_NAME" --query 'QueueUrl' --output text)
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

**Ver logs del worker**:
```bash
docker compose logs -f celery_worker
```

**Ver uso de recursos**:
```bash
docker stats celery_worker
```

### Salidas Esperadas

- Videos/min procesados por cada configuración
- Tiempo promedio de procesamiento por video
- Crecimiento de la cola (debería ser ~0 en modo sostenido)
- Saturación de recursos (CPU, disco, almacenamiento temporal)

## Estructura de Resultados

```
load_tests/
  results/
    escenario1_smoke_20241017_143022.html
    escenario1_ramp_100users_20241017_143500.html
    escenario2_burst_50MB_concurrency4_20241017_150000.log
    ...
```

## Resolución de Problemas

### Altas tasas de error

- Revisa logs de la API: `docker compose logs rest_api`
- Verifica conexiones a base de datos
- Verifica espacio en disco para subidas

### Cola del worker creciendo

- Aumenta la concurrencia de workers
- Verifica tiempo de procesamiento (ffmpeg)
- Confirma rendimiento del disco

### Prometheus no recolecta métricas

- Confirma que la API expone `/metrics`: `curl http://localhost:8080/api/metrics`
- Revisa los targets de Prometheus: http://localhost:9090/targets

### Errores de conexión en Locust

- Confirma que Nginx está haciendo proxy correctamente
- Verifica conectividad de red
- Revisa y corrige la URL del host en el comando

## Consejos

1. **Siempre ejecuta el smoke test primero** para validar que el entorno esté correcto.
2. **Monitorea Grafana en paralelo** durante las pruebas de carga.
3. **Guarda los reportes HTML** con nombres descriptivos.
4. **Documenta características del sistema** (CPU, RAM, disco) en los reportes de capacidad.
5. **Haz varias corridas** para comparar y obtener consistencia.
6. **Limpia datos de prueba** entre pruebas si es necesario:
   ```bash
   docker compose exec rest_api python -c "from app.core.database import SessionLocal; from app.models import Video; db = SessionLocal(); db.query(Video).filter(Video.task_id.like('mock-%')).delete(); db.commit()"
   ```

## Referencias

- [Documentación de Locust](https://docs.locust.io/)
- [Consultas Prometheus](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Documento de análisis de capacidad](../docs/entregas/entrega_1/analisis_capacidad.md)



