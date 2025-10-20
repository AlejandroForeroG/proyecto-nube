# Plan de Pruebas de Carga y Capacidad

## 1. Objetivo y Alcance

- **Objetivo general**: medir la capacidad de la plataforma para cumplir los SLO definidos, identificando cuellos de botella y configuraciones óptimas.
- **Alcance**:
  - **Escenario 1 (Capa Web)**: capacidad de la API usando `/api/videos/upload-mock` sin depender del worker.
  - **Escenario 2 (Worker)**: throughput de procesamiento de videos/minuto variando concurrencia y tamaños.

## 2. Criterios de Aceptación (SLOs)

- **Latencia p95** ≤ 1.0 s (Escenario 1)
- **Tasa de error** ≤ 5% (Escenario 1)
- **Éxito de tareas** ≥ 95% (Escenario 2)
- **Cola estable** (crecimiento ≈ 0 en modo sostenido, Escenario 2)

## 3. Entorno, Herramientas y Monitoreo

- **Infraestructura**: `docker compose up -d --build`
  - Servicios: FastAPI (`8000`), Nginx (`8080`), PostgreSQL (`5432`), Redis (`6379`), Celery Worker, Prometheus (`9090`), Grafana (`3001`).
- **Herramientas**: Locust, Prometheus, Grafana, scripts en `load_tests/`.
- **Monitoreo**:
  - Prometheus: `http://localhost:9090/targets` (target `fastapi` debe estar UP)
  - Grafana: `http://localhost:3001` (dashboard "FastAPI Load Testing Metrics")
  - Métricas API: `http://localhost:8080/metrics`
  - Recursos: `docker stats rest_api postgres redis celery_worker`

## 4. Datos de Prueba y Preparación

- **Archivos de prueba**: generados automáticamente por `inject_worker_tasks.py` (50MB, 100MB, 200MB) y ubicados en `/my-app/uploads` dentro del contenedor.
- **Semilla de DB (Escenario 2)**: crear `Video.id` en rango [10000..N] para evitar fallos por inexistencia del registro.
```bash
docker compose exec rest_api python -c "
from app.core.database import SessionLocal
from app.models.models import User, Video
from app.core.security import get_password_hash
db = SessionLocal()
user = db.query(User).filter(User.email=='loadtest@example.com').first()
if not user:
  user = User(email='loadtest@example.com', first_name='Load', last_name='Test', city='Bogotá', country='CO', hashed_password=get_password_hash('P@ssw0rd123!'))
  db.add(user); db.commit(); db.refresh(user)
for vid in range(10000, 10150):
  if not db.query(Video).filter(Video.id==vid).first():
    db.add(Video(id=vid, video_id=f'mock-{vid}', title='LoadTest', user_id=user.id, status='uploaded', is_public=False))
db.commit(); print('Seed OK')
"
```

## 5. Estrategia de Pruebas

### 5.1 Escenario 1 – Capacidad Capa Web (Locust)

- **Objetivo**: determinar usuarios concurrentes máximos cumpliendo SLOs, aislando al worker con `/api/videos/upload-mock`.
- **Host de prueba**: `http://localhost:8080`
- **Distribución de tareas** (según `locustfile_web.py`):
  - `upload_video_mock` (peso 10), `list_videos` (peso 2), `health_check` (peso 1)

Casos de prueba (headless):

1) Smoke (sanidad, 1 min)
```bash
locust -f load_tests/locustfile_web.py --users 5 --spawn-rate 5 --run-time 1m \
  --host http://localhost:8080 --headless
```

2) Ramp 100 usuarios (8 min)
```bash
locust -f load_tests/locustfile_web.py --users 100 --spawn-rate 0.55 --run-time 8m \
  --host http://localhost:8080 --headless --html load_tests/results/ramp_100users.html
```

5) Sostenida (80% de la capacidad hallada, 5 min)
```bash
locust -f load_tests/locustfile_web.py --users <80%> --spawn-rate <80%> --run-time 5m \
  --host http://localhost:8080 --headless --html load_tests/results/sustained_<n>users.html
```

Mediciones y éxito (por caso):
- p95 ≤ 1.0s, errores ≤ 5%.
- RPS pico y sostenido.
- Salud de servicios y ausencia de timeouts.

Artefactos:
- Reportes HTML en `load_tests/results/`.
- Capturas de Grafana en picos.

### 5.2 Escenario 2 – Throughput de Worker (Inyección directa)

- **Objetivo**: medir videos/min procesados variando concurrencia y tamaño.
- **Ajuste de concurrencia** del worker en `docker-compose.yml`:
```yaml
celery_worker:
  command: celery -A app.celery_worker.celery_app worker --loglevel=info --concurrency=1 --prefetch-multiplier=1
```
Reiniciar tras cada cambio:
```bash
docker compose restart celery_worker
```

Ejecuciones tipo (dentro del contenedor `rest_api`):

Burst 100×50MB
```bash
docker compose exec -e REDIS_URL=redis://redis:6379/0 -e UPLOAD_PATH=/my-app/uploads rest_api \
  python load_tests/inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor
```

Burst 50×100MB
```bash
docker compose exec -e REDIS_URL=redis://redis:6379/0 -e UPLOAD_PATH=/my-app/uploads rest_api \
  python load_tests/inject_worker_tasks.py --count 50 --size 100MB --mode burst --monitor
```

Sustained 50×100MB @10/min
```bash
docker compose exec -e REDIS_URL=redis://redis:6379/0 -e UPLOAD_PATH=/my-app/uploads rest_api \
  python load_tests/inject_worker_tasks.py --count 50 --size 100MB --mode sustained --rate 10 --monitor
```

Sustained 80×200MB @20/min
```bash
docker compose exec -e REDIS_URL=redis://redis:6379/0 -e UPLOAD_PATH=/my-app/uploads rest_api \
  python load_tests/inject_worker_tasks.py --count 80 --size 200MB --mode sustained --rate 20 --monitor
```

Monitoreo durante la ejecución:
- Cola Redis: `docker compose exec redis redis-cli LLEN celery`
- Logs worker: `docker compose logs -f celery_worker`
- Recursos: `docker stats celery_worker`

KPIs y éxito:
- Throughput (videos/min) por configuración.
- Tiempo promedio de procesamiento por video.
- Éxito ≥ 95% y cola ≈ 0 en sostenido.

Artefactos:
- Logs de tareas en `load_tests/results/worker_tasks_*.log`.
- Capturas/observaciones en `docs/entregas/entrega_1/analisis_capacidad.md`.

## 6. Matriz de Pruebas Resumida

| Escenario | Tamaño | Concurrencia | Modo       | Cantidad | Criterios de éxito |
|-----------|--------|--------------|------------|----------|--------------------|
| Web       | N/A    | 5            | Smoke      | 1m       | p95≤1s, err≤5%     |
| Web       | N/A    | 100          | Ramp       | 8m       | p95≤1s, err≤5%     |
| Web       | N/A    | 200          | Ramp       | 8m       | p95≤1s, err≤5%     |
| Web       | N/A    | 300          | Ramp       | 8m       | p95≤1s, err≤5%     |
| Web       | N/A    | 80% máx      | Sostenida  | 5m       | Estable, SLO OK    |
| Worker    | 50MB   | 1,2,4        | Burst      | 100      | éxito≥95%          |
| Worker    | 100MB  | 1,2,4        | Burst      | 50       | éxito≥95%          |
| Worker    | 200MB  | 1,2,4        | Sostenida  | 20/40/80 | cola≈0, éxito≥95%  |

## 7. Recolección de Resultados y Documentación

- Guardar reportes HTML de Locust en `load_tests/results/`.
- Guardar logs de inyección en `load_tests/results/`.
- Exportar capturas de Grafana (picos y sostenido).
- Completar plantillas en `docs/entregas/entrega_1/analisis_capacidad.md` (reemplazar `[TBD]`).

## 8. Riesgos y Mitigaciones

- I/O de disco del worker limita throughput → usar NVMe/local, ajustar concurrencia.
- Falta de registros `Video` → ejecutar semilla antes del Escenario 2.
- Paths de archivos incorrectos → usar `UPLOAD_PATH=/my-app/uploads` y volúmenes montados.
- Métricas no visibles → validar `/metrics` y targets de Prometheus.

## 9. Criterios de Salida

- Todos los casos ejecutados y artefactos almacenados.
- SLOs evaluados; capacidad y cuellos de botella identificados.
- Documento de análisis completado con conclusiones y recomendaciones.

## 10. Roles y Cronograma

- **Roles**: 1 operador pruebas, 1 observabilidad, 1 analista.
- **Cronograma estimado**:
  - Día 1: Setup y smoke.
  - Día 2: Escenario 1 (ramp y sostenida).
  - Día 3: Escenario 2 (matriz).
  - Día 4: Análisis y documentación.


