# Informe de Análisis de Capacidad
## Pruebas de Carga en la Plataforma de Procesamiento de Videos

**Proyecto:** Plataforma de Procesamiento de Videos (FastAPI + Celery + Nginx)  
**Integrantes del equipo:**
- Alejandro Forero Gomez
- David Armando Rodríguez Varón
- Juan Sebastián Sánchez Tabares
- Yesid Arley Marin Rivera

**Fecha:** [Por completar tras la ejecución de pruebas]  
**Versión:** 1.0

---

## Tabla de Contenidos

1. [Infraestructura Utilizada](#infraestructura-utilizada)
2. [Metodología de Pruebas](#metodologia-de-pruebas)
3. [Escenario 1: Capacidad Capa Web](#escenario-1-capacidad-capa-web)
4. [Escenario 2: Throughput de Worker](#escenario-2-throughput-de-worker)
5. [Análisis de Cuellos de Botella](#análisis-de-cuellos-de-botella)
6. [Conclusiones y Recomendaciones](#conclusiones-y-recomendaciones)
7. [Apéndices](#apéndices)

---
## Infraestructura Utilizada

### Especificaciones del Entorno de Pruebas

#### Hardware
- **CPU:** [Ej: Intel Core i7-10700K, 8 núcleos @ 3.8GHz]
- **RAM:** [Ej: 32 GB DDR4]
- **Almacenamiento:** [Ej: 1TB NVMe SSD]
- **Red:** [Ej: 1Gbps Ethernet / Local]

#### Stack de Software

| Componente | Versión | Configuración |
|------------|---------|--------------|
| Sistema Operativo | [Ej: Ubuntu 22.04 LTS] | |
| Docker | [Ej: 24.0.6] | |
| Docker Compose | [Ej: 2.21.0] | |
| FastAPI | 0.118.0 | workers Uvicorn |
| PostgreSQL | 16-alpine | Conexiones |
| Redis | 7-alpine | Memoria |
| Celery Worker | 5.3.4 | Concurrencia: [según la prueba] |
| Nginx | alpine | Procesos worker |

#### Stack de Observabilidad

- **Prometheus**: v2.x - Colección de métricas (intervalo: 5s)
- **Grafana**: v10.x - Visualización y dashboards
- **Locust**: v2.31.8 - Generación de carga

### Topología de Red

```
[Locust Load Generator]
         ↓
    [Nginx :8080]
         ↓
   [FastAPI :8000] ←→ [PostgreSQL :5432]
         ↓
    [Redis :6379]
         ↓
  [Celery Worker]
         ↓
   [Almacenamiento Archivos]
```

### Configuración de Monitoreo

**Scrape de Prometheus:**
```yaml
scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['rest_api:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

**Dashboards Grafana:**
- FastAPI Load Testing Metrics (dashboard custom)
- Métricas: tasa de requests, percentiles de latencia, tasa de errores

---

## Metodología de Pruebas

### Escenario 1: Capacidad Capa Web

#### Objetivo
Determinar el máximo de usuarios concurrentes que soporta el endpoint de subida de videos sin violar los SLO, asegurando que la capa worker no sea factor limitante.

#### Estrategia
- **Desacople:** Uso del endpoint `/api/videos/upload-mock` (no encola tarea Celery).
- **Carga realista:** Subidas de archivos de video de 1MB simulando comportamiento real.
- **Autenticación:** Cada usuario virtual se autentica y conserva un token JWT.

#### Fases de la Prueba

##### 1. Smoke Test (Chequeo Inicial)
- **Propósito:** Verificar salud del sistema y telemetría.
- **Configuración:**
  - Usuarios: 5
  - Duración: 1 minuto
  - Tasa de aparición: 5 usuarios/segundo
- **Criterio de éxito:** Sin errores, métricas recolectándose.

##### 2. Ramp Test (Descubrimiento de Capacidad)
- **Propósito:** Determinar punto de quiebre aumentando la carga progresivamente.
- **Configuraciones:**
  - Prueba A: 100 usuarios (3min ramp + 5min sostenido)
  - Prueba B: 200 usuarios (3min ramp + 5min sostenido)
  - Prueba C: 300 usuarios (3min ramp + 5min sostenido)
  - [Continuar hasta observar degradación]
- **Tasa de aparición:** X usuarios / 180s

##### 3. Sostenido (Estabilidad)
- **Propósito:** Confirmar estabilidad al 80% de la capacidad máxima hallada.
- **Configuración:**
  - Usuarios: 80% de la capacidad máxima
  - Duración: 5 minutos
  - Todos los usuarios en simultáneo

#### Objetivos de Nivel de Servicio (SLOs)

| Métrica     | Meta       | Medición                       |
|-------------|------------|--------------------------------|
| Latencia p95| ≤ 1.0s     | Percentil 95 respuesta         |
| Tasa errores| ≤ 5%       | (4xx + 5xx) / total requests   |
| Disponibilidad | ≥ 99%   | Respuestas exitosas / total    |

#### Perfil de Carga

**Distribución de tareas** (pesos Locust):
- `upload_video_mock`: Peso 10 (principal)
- `list_videos`: Peso 2 (secundario)
- `health_check`: Peso 1 (mínimo)

---

### Escenario 2: Throughput de Worker

#### Objetivo
Medir cuántos videos por minuto pueden ser procesados por los workers bajo diferentes niveles de concurrencia y tamaños de archivo.

#### Estrategia
- **Bypass capa web:** Inyección directa de tareas en Redis.
- **Variables controladas:** Tamaño del video, concurrencia worker.
- **Métrica:** Tiempo desde enqueue hasta finalización.

#### Matriz de Pruebas

| Tamaño Video | Workers | Tipo de Prueba | Duración/Cantidad         |
|--------------|---------|----------------|--------------------------|
| 50MB         | 1       | Burst          | 100 tareas               |
| 50MB         | 2       | Burst          | 100 tareas               |
| 50MB         | 4       | Burst          | 100 tareas               |
| 100MB        | 1       | Burst          | 50 tareas                |
| 100MB        | 2       | Burst          | 50 tareas                |
| 100MB        | 4       | Burst          | 50 tareas                |
| 200MB        | 1       | Sostenido      | 20 tareas @ 5/min        |
| 200MB        | 2       | Sostenido      | 40 tareas @ 10/min       |
| 200MB        | 4       | Sostenido      | 80 tareas @ 20/min       |

#### Pipeline de Procesamiento (ffmpeg)

Cada video pasa por:
1. **Recorte** a 30 segundos
2. **Escalado** a 720p @ 30fps
3. **Eliminación de audio**
4. **Watermark** (esquina superior derecha)
5. **Intro/Outro** (3s c/u desde imagen estática)

#### Métricas colectadas

- **Throughput:** videos/minuto procesados
- **Service Time:** tiempo promedio por video (s)
- **Crecimiento de la cola:** tareas/min en cola - tareas/min completadas
- **Uso de recursos:** CPU, RAM, I/O disco

#### Criterios de éxito

- **Capacidad nominal:** Throughput estable sin crecimiento sostenido de la cola.
- **Estabilidad:** Tendencia de cola ≈ 0 durante la duración.
- **Sin fallos:** ≥ 95% tareas exitosas.

---

## Escenario 1: Capacidad Capa Web

### Ejecución de las Pruebas

#### Resultados Smoke Test

**Comando de ejecución:**
```bash
locust -f locustfile_web.py --users 5 --spawn-rate 5 --run-time 1m \
  --host http://localhost:8080 --headless
```

**Resultados:**

| Métrica       | Valor  |
|---------------|--------|
| RPS           | 5  |
| p50 Latencia  | 200 ms |
| p95 Latencia  | 200 ms |
| p99 Latencia  | 200 ms |
| Errores (%)   | 0%  |
| Estado        | APROBADO |

**Observaciones:**
- Todo operativo sin errores
---

#### Ramp Test A: 100 usuarios

**Comando:**
```bash
locust -f locustfile_web.py --users 100 --spawn-rate 0.55 --run-time 8m \
  --host http://localhost:8080 --headless --html reports/ramp_100users.html
```

**Resultados:**

| Métrica          | Valor     | SLO       | Estado       |
|------------------|-----------|-----------|--------------|
| RPS Pico         | 10     | -         | -            |
| p99 Latencia     | 2000 ms  | -         | -            |
| Tasa de errores  | 0%    | ≤ 5%      | ✓        |
| Resp. Promedio   | 2400 ms  | -         | -            |


**Uso de recursos:**

| Componente | CPU % | RAM % | Notas           |
|------------|-------|-------|-----------------|
| rest_api   | 80% | 22% | [Ej: Estable]   |
| postgres   | 25% | 10% | [Ej: Bajo uso]  |
| nginx      | 5 | [TBD] | [Ej: Mínimo]    |

**Observaciones:**
- cuellos de botella a los 60 usuarios empieza 
a presentar retrasos de hasta 2 segundos manteniendose
---


#### Test Sostenido: 48 usuarios 

**Comando:**
```bash
locust -f locustfile_web.py --users 40 --spawn-rate 0.266 --run-time 5m \
  --host http://localhost:8080 --headless --html reports/sustained_38users.html
```

**Resultados:**

| Métrica        | Valor    | SLO      | Estado      |
|----------------|----------|----------|-------------|
| RPS            | 10    | -        | -           |
| p95 Latencia   | 600 ms | ≤1000ms  | ✓       |
| Tasa de errores| 0%   | ≤5%      | ✓       |
| Estabilidad    | Estable | Estable | ✓  |

**Observaciones:**
- [Ej.: Sistema estable los 5 minutos.]
- [Ej.: Sin degradación.]

---

### Resumen de Capacidad - Escenario 1

**Capacidad máxima alcanzada:**  
- **Usuarios concurrentes soportados:** 48  
- **RPS sostenido:** 10 req/s  
- **Cumplimiento SLO:** APROBADO

**Métricas en la prueba límite de capacidad:**

| Métrica      | Valor   | SLO        | Estado  |
|--------------|---------|------------|---------|
| Usuarios     | 48      | -          | -       |
| RPS          | 10      | -          | -       |
| p50 Latencia | 400 ms  | -          | ✓       |
| p95 Latencia | 600 ms  | ≤1000ms    | ✓       |
| p99 Latencia | 2000 ms | -          | -       |
| Tasa errores | 0%      | ≤5%        | ✓       |


#### Curva Carga vs Capacidad

```
smoke https://drive.google.com/file/d/1bqwdkJzfkJKyH-ZeAaoJ_M48veYXHGks/view?usp=sharing

ramp: https://drive.google.com/file/d/1HGlbX0xpFquYr7K7y1AmgxmfjNx5NJ1V/view?usp=sharing

sustained: https://drive.google.com/file/d/1a80OycXHq1yiyX88kKR637UdY6iStT67/view?usp=sharing
```

#### Primer punto de degradación

**Componente:** Res_api latencia  
**Umbral:** 100 usuarios 60% 
**Impacto:** 95% de los usuarios con 2400 ms en respuesta

---

## Escenario 2: Throughput de Worker

Para esta primera iteracion no se lograorn completar estas pruebas

## Información de Pruebas

### Comandos de referencia

#### Escenario 1

```bash
# Smoke test
locust -f locustfile_web.py --users 5 --spawn-rate 5 --run-time 1m \
  --host http://localhost:8080 --headless

# Ramp test - 100 usuarios
locust -f locustfile_web.py --users 100 --spawn-rate 0.55 --run-time 8m \
  --host http://localhost:8080 --headless --html reports/ramp_100users.html

# Test sostenido
locust -f locustfile_web.py --users 80 --spawn-rate 80 --run-time 5m \
  --host http://localhost:8080 --headless --html reports/sustained_80users.html
```

#### Escenario 2

```bash
# Burst test - 50MB
python inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor

# Sostenido - 200MB
python inject_worker_tasks.py --count 20 --size 200MB --mode sustained --rate 5 --monitor
```

### Consultas Prometheus

```promql
# Tasa de requests
rate(http_requests_total[1m])

# Latencia p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[1m]))

# Porcentaje de errores
(sum(rate(http_requests_total{status=~"4..|5.."}[1m])) / sum(rate(http_requests_total[1m]))) * 100

# Requests por endpoint
sum by(handler) (rate(http_requests_total[1m]))
```

### Comandos de monitoreo

```bash
# Stats docker
docker stats --no-stream

# CPU y RAM de contenedor
docker stats rest_api celery_worker postgres redis --no-stream

# Longitud cola Redis
docker compose exec redis redis-cli LLEN celery

# Logs worker
docker compose logs -f celery_worker --tail=100

# Conexiones DB
docker compose exec postgres psql -U app_user -d app_db -c "SELECT count(*) FROM pg_stat_activity;"
```

### Limpieza de datos de prueba

```bash
# Eliminar videos mock
docker compose exec rest_api python -c "
from app.core.database import SessionLocal
from app.models import Video
db = SessionLocal()
deleted = db.query(Video).filter(Video.task_id.like('mock-%')).delete()
db.commit()
print(f'Deleted {deleted} mock video records')
"

# Limpiar cola Redis
docker compose exec redis redis-cli FLUSHDB
```

### Configuración de entorno

**Archivo `.env` usado en pruebas:**
```bash
DATABASE_URL=postgresql+psycopg2://app_user:app_password@postgres:5432/app_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=supersecretkeyfroloadtesting
TESTING=false
CELERY_EAGER=0
MAX_FILE_SIZE=104857600  # 100MB
UPLOAD_PATH=/my-app/uploads
PROCESSED_PATH=/my-app/processed
```

