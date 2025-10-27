## Pruebas de carga – Entrega 2 (Capacity Planning)

### 1) Infraestructura utilizada (Entrega 2)
- Web Server: FastAPI + Nginx (EC2, 2 vCPU, 2 GiB RAM, 50 GiB disco)
- Worker: Celery + Redis (EC2, 2 vCPU, 2 GiB RAM, 50 GiB disco)
- File Server: NFS v4.1 (EC2, 2 vCPU, 2 GiB RAM, 50 GiB disco)
- Base de datos: Amazon RDS (PostgreSQL)
- Observabilidad: Prometheus + Grafana (ver `docs/entregas/entrega_2/entrega_2.md`)

Topología resumida: Nginx → FastAPI → (RDS) y (Redis←Celery Worker) y (NFS para `uploads/`/`processed/`).

### 2) Metodología de pruebas
Las pruebas siguen el enfoque definido en `docs/entregas/entrega_1/plan_pruebas.md` y el análisis de capacidad en `docs/entregas/entrega_1/analisis_capacidad.md`.

- SLOs:
  - p95 latencia ≤ 1s
  - errores ≤ 5%
  - disponibilidad ≥ 99%
- Métricas leídas: RPS, p50/p95/p99, errores, CPU/RAM, I/O y crecimiento de cola.

### 3) Configuración de las pruebas (Escenario 1)
- Endpoint principal: `/api/videos/upload-mock` (evita cargar el Worker para aislar capa Web).
- Autenticación: JWT por usuario virtual.
- Archivo simulado: 1 MB.
- Perfiles Locust: `upload_video_mock` (peso 10), `list_videos` (2), `health_check` (1).
- Perfiles de ejecución:
  - Smoke: 5 usuarios, 1m, `--spawn-rate 5`.
  - Ramp: 100 usuarios, 8m (ramp + sostenido), `--spawn-rate 0.55`.
  - Sostenido: 36 usuarios concurrentes estables (capacidad observada en E2).

### 4) Resultados detallados – Escenario 1

#### 4.1 Smoke (5 usuarios)
- p95 latencia: 600 ms (Entr. 2) vs 100 ms (Entr. 1)
- RPS: acorde a 5 usuarios, sin errores.
- Observación: incremento de latencia con respecto a las pruebas en local

#### 4.2 Ramp (100 usuarios)
- Inicio de degradación: 47 usuarios (Entr. 2) vs 60 (Entr. 1)
- p99 picos ~2s en el umbral de degradación; errores dentro del SLO.
- Observación: el punto de quiebre se reduce a 47 usuarios concurrentes revisar límites de workers Uvicorn, conexión RDS y NFS.

#### 4.3 Sostenido (capacidad estable)
- Concurrencia estable: 36 usuarios (Entr. 2) vs 48 (Entr. 1)
- p95 latencia ≈ 600–800 ms; errores ≤ 5%.
- Observación: menor capacidad sostenida respecto a la entrega previa.

#### 4.4 Cuadro comparativo
| Caso | Entrega 1 | Entrega 2 | Observación |
|---|---:|---:|---|
| Latencia con 5 usuarios | 100 ms | 600 ms | Mayor latencia base |
| Ramp (100) – inicio degradación | 60 usuarios | 47 usuarios | Degradación más temprana |
| Sostenido – usuarios estables | 48 usuarios | 36 usuarios | Menor capacidad |

Evidencias: `load_tests/results/36_sustainedusers.html`, `load_tests/results/48_sustainedusers.html`, `load_tests/results/ramp_100users.html`.

### 5) Resultados – Escenario 2 (Throughput del Worker)

#### 5.1 Objetivo y alcance
Medir la capacidad de procesamiento del Worker (Celery + ffmpeg) y validar estabilidad de la cola en distintos niveles de concurrencia y tamaños de archivo. Se inyectan tareas directamente en la cola para aislar la capa de procesamiento.

#### 5.2 SLOs del escenario
- Éxito de tareas ≥ 95% (sin fallas en pipeline ffmpeg ni timeouts).
- Cola estable en modo sostenido (backlog ≈ 0 tras periodo de calentamiento).
- Uso de CPU en el Worker ≤ 85% promedio sostenido; sin thrashing de memoria.

#### 5.3 Parámetros y preparación
- Tamaños de prueba: 50 MB, 100 MB, 200 MB.
- Concurrencia del Worker: 1, 2, 4 (ajustable en `compose.worker.yml`).
- Prefetch: `--prefetch-multiplier=1` (evita acaparamiento de tareas largas).
- Tiempos de recorte: el pipeline recorta a 30s y luego aplica escalado, muteo y watermark.

Ajuste de concurrencia (ejemplo):

```yaml
# compose.worker.yml
celery_worker:
  command: celery -A app.celery_worker.celery_app worker --loglevel=info --concurrency=2 --prefetch-multiplier=1
```

Reinicio tras cambio:

```bash
docker compose -f compose.worker.yml restart celery_worker
```

Generación de archivos de prueba (opcional, si no se cuenta con videos de muestra):

```bash
# 30s a 720p con patrón de prueba (requiere ffmpeg)
ffmpeg -f lavfi -i testsrc=size=1280x720:rate=30 -t 30 -c:v libx264 -pix_fmt yuv420p ./load_tests/test_files/test_30s_720p.mp4 -y
```

#### 5.4 Metodología de inyección
- Inyección directa en Celery usando `load_tests/inject_worker_tasks.py`.
- Modos:
  - Burst: somete N tareas inmediatamente (detecta saturación).
  - Sustained: tasa controlada (tareas/min) para verificar estabilidad de cola.

Comandos ejemplo:

```bash
python load_tests/inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor

python load_tests/inject_worker_tasks.py --count 50 --size 100MB --mode sustained --rate 10 --monitor
```

Monitoreo recomendado durante las pruebas:

```bash
docker compose exec redis redis-cli
> LLEN celery

# Logs  recursos del worker
docker compose logs -f celery_worker
docker stats celery_worker
```

#### 5.5 Resultados y observaciones
- Concurrencia = 1: utilización de CPU alta y tiempos de procesamiento consistentes; throughput limitado por CPU (transcodificación ffmpeg).
- Concurrencia = 2: mejora moderada del throughput hasta cercanías a 2 vCPU; la latencia por tarea puede aumentar si hay contención de CPU/IO.
- Concurrencia = 4: sobre-suscripción de CPU en instancias de 2 vCPU; no mejora el throughput efectivo y puede aumentar la latencia por tarea, preferible escalar horizontalmente más workers con baja concurrencia.
- Tamaño de archivo: el tiempo de proceso crece principalmente por I/O de lectura/escritura y codificación, al recortar a 30s, el costo de transcodificación predomina sobre el tamaño b del.
- Cola en sostenido: estable si la tasa de llegada ≤ throughput medido; de lo contrario, backlog creciente y picos de uso de CPU/IO.

Evidencias esperadas:
- Registros de inyección/monitoreo en `load_tests/results/worker_tasks_*.log`.
- Capturas de Grafana/Prometheus de CPU, uso de disco y métricas de cola.

Resumen de hallazgos del escenario:
- Ajustar `--concurrency` al número de vCPU (o menor) y escalar horizontalmente en lugar de sobre-suscribir CPU.
- Mantener `--prefetch-multiplier=1` para trabajos largos de video.
- Validar rendimiento del almacenamiento compartido (NFS/EFS); considerar S3 para estáticos/descargas una vez procesados.

### 6) Análisis de cuellos de botella (hipótesis y hallazgos)
- Capa Web (FastAPI/Uvicorn): número de workers/hilos por defecto puede limitar RPS; revisar configuración.
- NFS: latencia al acceder a `uploads/`/`processed/` puede impactar tiempos; evaluar tamaños de chunk y fsync selectivo.
- RDS (PostgreSQL): latencia de red y pool de conexiones; validar tamaño del pool y consultas N+1.
- Redis/Celery: no fue el foco del Escenario 1; monitorear en Escenario 2 (throughput de procesamiento).
- Nginx: confirmar límites de conexiones y buffers.

### 7) Conclusiones y ajustes a futuro
- Si queremos soportar más usuarios, debemos pensar en estrategias de escalabilidad horizontal o vertical para soportar grandes flujos de datos y evitar que el sistema se caiga.
- Acciones sugeridas (priorizadas):
  1. Escalado horizontal de Web/API detrás de balanceador (2→3 réplicas) y ajustar workers Uvicorn.
  2. Aumentar réplicas de Celery y `--concurrency`; migrar Redis a servicio administrado.
  3. Optimizar almacenamiento: NFS tuning o evaluar EFS/S3 para estáticos y uploads.
  4. Ajustar pool de conexiones a RDS y revisar índices/consultas críticas.
  5. Añadir CDN para `/processed/` y caching de respuestas frecuentes.
  6. Implementar rate limiting y backpressure para proteger la API.
  7. Observabilidad: dashboards y alertas sobre p95/p99, RPS y colas.



