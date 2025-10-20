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

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Infraestructura Utilizada](#infraestructura-utilizada)
3. [Metodología de Pruebas](#metodologia-de-pruebas)
4. [Escenario 1: Capacidad Capa Web](#escenario-1-capacidad-capa-web)
5. [Escenario 2: Throughput de Worker](#escenario-2-throughput-de-worker)
6. [Análisis de Cuellos de Botella](#análisis-de-cuellos-de-botella)
7. [Conclusiones y Recomendaciones](#conclusiones-y-recomendaciones)
8. [Apéndices](#apéndices)

---

## Resumen Ejecutivo

### Propósito

Este documento expone los resultados de las pruebas de carga realizadas sobre la plataforma de procesamiento de videos para determinar:
1. Usuarios concurrentes máximos soportados por la capa web.
2. Throughput de procesamiento de la capa de workers (videos/minuto).
3. Principales cuellos de botella y limitaciones detectadas.

### Hallazgos Clave

> **Nota:** Completar tras ejecución de pruebas.

| Métrica | Resultado | SLO | Estado |
|---------|-----------|-----|--------|
| **Capa Web** |
| Usuarios Concurrentes Máximos | [TBD] usuarios | - | - |
| RPS a máxima capacidad | [TBD] req/s | - | - |
| Latencia p95 | [TBD] ms | ≤ 1000ms | [APROBADO/RECHAZADO] |
| Tasa de errores | [TBD]% | ≤ 5% | [APROBADO/RECHAZADO] |
| **Capa Worker** |
| Throughput (50MB) | [TBD] videos/min | - | - |
| Throughput (100MB) | [TBD] videos/min | - | - |
| Throughput (200MB) | [TBD] videos/min | - | - |
| Concurrencia Óptima | [TBD] workers | - | - |

### Principales Cuellos de Botella Identificados

1. **[Nombre del Componente]**: [Descripción]
2. **[Nombre del Componente]**: [Descripción]
3. **[Nombre del Componente]**: [Descripción]

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
| FastAPI | 0.118.0 | workers Uvicorn: [TBD] |
| PostgreSQL | 16-alpine | Conexiones: [TBD] |
| Redis | 7-alpine | Memoria: [TBD] |
| Celery Worker | 5.3.4 | Concurrencia: [según la prueba] |
| Nginx | alpine | Procesos worker: [TBD] |

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

### Ejecución de Pruebas

#### Resultados Matriz de Configuración

##### Prueba 1: Videos 50MB, 1 Worker

**Comando:**
```bash
python inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor
```

**Resultados:**

| Métrica               | Valor     |
|-----------------------|-----------|
| Tareas Totales        | 100       |
| Tiempo Total          | [TBD] min |
| Throughput            | [TBD] vid/min |
| Tiempo promedio proc. | [TBD] s   |
| Tasa de éxito         | [TBD]%    |
| Cola pico             | [TBD]     |

**Observaciones:**
- [Procesamiento secuencial, sin paralelismo.]
- [CPU: 85%, I/O wait: 15%]

---

##### Prueba 2: 50MB, 2 Workers

[Repetir estructura]

---

##### Prueba 3: 50MB, 4 Workers

[Repetir estructura]

---

##### Prueba 4-6: 100MB (1, 2, 4 workers)

[Repetir estructura por configuración]

---

##### Prueba 7-9: 200MB (Sostenido)

**Prueba 7: 200MB, 1 Worker, Sostenido**

**Comando:**
```bash
python inject_worker_tasks.py --count 20 --size 200MB --mode sustained --rate 5 --monitor
```

**Resultados:**

| Métrica        | Valor  |
|----------------|--------|
| Tasa objetivo  | 5 tareas/min |
| Throughput real| [TBD] vid/min|
| Crecimiento cola| [TBD] (objetivo ≈ 0) |
| Tiempo promedio | [TBD] s/vid  |
| Tasa éxito     | [TBD]% |

**Comportamiento de cola:**
- Inicial: [TBD]
- 2 min: [TBD]
- 5 min: [TBD]
- Final: [TBD]
- **Tendencia:** [Creciendo/Estable/Disminuyendo]

---

### Resumen Throughput - Escenario 2

#### Tabla de Capacidad

| Tamaño | Workers | Modo     | Throughput (vid/min) | Tiempo prom (s) | ¿Cola estable? |
|--------|---------|----------|----------------------|-----------------|---------------|
| 50MB   | 1       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 50MB   | 2       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 50MB   | 4       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 100MB  | 1       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 100MB  | 2       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 100MB  | 4       | Burst    | [TBD]                | [TBD]           | [Sí/No]       |
| 200MB  | 1       | Sostenido| [TBD]                | [TBD]           | [Sí/No]       |
| 200MB  | 2       | Sostenido| [TBD]                | [TBD]           | [Sí/No]       |
| 200MB  | 4       | Sostenido| [TBD]                | [TBD]           | [Sí/No]       |

#### Configuración Óptima

**Setup Recomendado:**
- **Concurrencia:** [TBD] workers
- **Throughput Esperado:** [TBD] videos/min
- **Tiempo promedio:** [TBD] s/video
- **Justificación:** [Ej: Mejor balance entre throughput y uso de recursos]

#### Escalabilidad

**Ley de Amdahl:**

```
Speedup = 1 / ((1 - P) + P/N)

P = fracción paralelizable
N = número de workers
```

**Escalamiento observado:**

| Workers | Speedup teórico | Observado | Eficiencia |
|---------|----------------|-----------|------------|
|   1     | 1.0x           | 1.0x      | 100%       |
|   2     | 2.0x           | [TBD]x    | [TBD]%     |
|   4     | 4.0x           | [TBD]x    | [TBD]%     |

**Cuello de botella:** [Ej: I/O disco saturado a 4 workers]

---

## Análisis de Cuellos de Botella

### Escenario 1: Bottlenecks Capa Web

#### Cuello principal

**Componente:** [Ej: CPU FastAPI]

**Evidencia:**
- Con [X] usuarios, CPU llegó a [Y]%
- Latencia p95 subió de [A]ms a [B]ms
- Salida docker stats: [dato relevante]

**Impacto:**
- Capacidad máxima limitada a [X] usuarios
- Sobre este punto se violan SLOs

**Estrategias de mitigación:**
1. [Ej.: Aumentar workers Uvicorn]
2. [Ej.: Optimizar queries, agregar índices]
3. [Ej.: Mejorar pool conexiones]
4. [Ej.: Escalar horizontal con load balancer]

---

#### Bottlenecks secundarios

**Componente:** [Ej: Pool de Conexión DB]

**Evidencia:**
- Pool agotado con [X] conexiones.
- Logs "too many connections".

**Mitigación:**
- Aumentar `SQLALCHEMY_POOL_SIZE`
- Uso adecuado de pooling en la aplicación

---

### Escenario 2: Bottlenecks Worker

#### Cuello principal

**Componente:** [Ej: I/O disco temporal de ffmpeg]

**Evidencia:**
- I/O wait alto: [X]%
- Tiempo de procesamiento crece no lineal vs concurrencia
- iostat: [dato relevante]

**Impacto:**
- Retorno decreciente sobre [N] workers
- Throughput se estabiliza en [X] videos/min

**Estrategias de mitigación:**
1. [Ej.: Usar tmpfs (RAM disk) para temporales]
2. [Ej.: Optimizar presets ffmpeg]
3. [Ej.: Separar workers en distintos servidores]

---

#### Desglose procesamiento ffmpeg

| Etapa            | Tiempo (s) | % del total |
|------------------|------------|-------------|
| Recorte 30s      | [TBD]      | [TBD]%      |
| Escalado 720p    | [TBD]      | [TBD]%      |
| Quitar audio     | [TBD]      | [TBD]%      |
| Agregar watermark| [TBD]      | [TBD]%      |
| Intro/Outro      | [TBD]      | [TBD]%      |
| **Total**        | [TBD]      | 100%        |

**Oportunidades de optimización:**
- [Ej: Pre-generar intro/outro si toma >30% del tiempo]
- [Ej: Usar aceleración hardware si es posible]

---

## Conclusiones y Recomendaciones

### Principales hallazgos

1. **Capacidad capa web**
   - Soporta hasta [X] usuarios concurrentes con SLOs cumplidos.
   - RPS sostenido: [Y] req/s.
   - Cuello principal: [componente].
2. **Throughput de worker**
   - Óptimo: [N] workers, [X] videos/min.
   - Escala lineal hasta [N] workers, luego cuellos de I/O.
3. **Cumplimiento SLO**
   - Latencia p95 ✓ hasta [X] usuarios.
   - Tasa de errores siempre <5%.

### Planeación de capacidad

#### Capacidad actual

**Capa Web:**
- **Recomendación prod:** 70% de máx = [X] usuarios
- **Margen de seguridad:** 30%
- **RPS esperado:** [Y] req/s

**Worker:**
- **Recomendación prod:** [N] workers a [X] videos/min
- **Monitoreo:** Alertar si cola > [umbral]
- **Escalar si:** crecimiento sostenido > [umbral]

#### Proyección de crecimiento (6 meses)

| Métrica      | Actual | +50% | +100% | Acción       |
|--------------|--------|------|-------|-------------|
| Pico usuarios| [X]    |[X*1.5]|[X*2]| [Escalado]  |
| Videos/día   | [Y]    |[Y*1.5]|[Y*2]| [Más workers]|

### Recomendaciones de optimización

#### Prioridad alta

1. **[Optimización 1]**
   - **Problema:** [describe]
   - **Impacto:** [rendimiento]
   - **Solución:** [explicación]
   - **Mejora esperada:** [ej: -20% latencia]
   - **Esfuerzo:** [Bajo/Medio/Alto]

2. **[Optimización 2]**
   - [estructura similar]

#### Prioridad media
3. **[Optimización 3]**
4. **[Optimización 4]**

#### Baja prioridad
5. **[Optimización 5]**

### Escalado de infraestructura

#### Horizontal

**Capa Web:**
```yaml
# Balanceo con múltiples instancias de API
nginx:
  upstream backend {
    server rest_api_1:8000;
    server rest_api_2:8000;
    server rest_api_3:8000;
  }
```

**Worker:**
```yaml
# Escalar workers independientemente
celery_worker:
  deploy:
    replicas: 4
```

#### Vertical

**Cuando escalar:**
- CPU > 70% sostenido
- RAM > 80% sostenido
- I/O disco > 20%

**Specs recomendadas:**
- CPU: [Ej: 16 cores API]
- RAM: [Ej: 64GB workers]
- Disco: [Ej: NVMe para temporales]

### Monitoreo y alertas

**Production monitoring:**

```yaml
alerts:
  - name: HighLatency
    condition: p95_latency > 1000ms for 5m
    action: Escalar API horizontal
  
  - name: WorkerQueueGrowth
    condition: queue_length creciendo 10m
    action: Añadir worker
  
  - name: HighErrorRate
    condition: error_rate >5% for 2m
    action: Notificar a ingeniero on-call
```

### Análisis de Costos

**Costo Infraestructura actual:**
- [Ej: AWS t3.xlarge API: $X/mes]
- [Ej: c5.2xlarge Workers: $Y/mes]
- [Ej: RDS PostgreSQL: $Z/mes]
- **Total**: $[Total]/mes

**Coste escalando:**
- 2x capacidad: $[Total]/mes (+[X]%)
- 4x capacidad: $[Total]/mes (+[Y]%)

---

## Apéndices

### Apéndice A: Comandos de referencia

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

### Apéndice B: Consultas Prometheus

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

### Apéndice C: Comandos de monitoreo

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

### Apéndice D: Limpieza de datos de prueba

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

### Apéndice E: Configuración de entorno

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

### Apéndice F: Dashboard JSON Grafana

[Enlace a dashboard exportado o embed si es pequeño]

### Apéndice G: Capturas de pantalla

> **Adjuntar capturas relevantes:**
> - Locust UI bajo carga máxima.
> - Gráficas de Grafana (latencia, errores).
> - Resultados Prometheus.
> - docker stats.

---
