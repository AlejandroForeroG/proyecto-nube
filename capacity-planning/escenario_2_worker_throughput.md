## Escenario 2 — Rendimiento de la capa Worker (SQS)

Objetivo: medir cuántos videos por minuto procesa el/los worker(s) a distintos niveles de paralelismo y tamaños de archivo, con broker Celery sobre Amazon SQS.

### Prerrequisitos
- Celery Worker configurado con SQS:
  - `app/celery_worker.py` usa `broker="sqs://"` y `task_default_queue` en `settings.SQS_QUEUE_NAME`.
  - Variables en `.env`:
    - `AWS_REGION=<us-east-1>` (o tu región)
    - `SQS_QUEUE_NAME=<nombre-cola>`
    - Credenciales AWS exportadas en el ambiente del contenedor/host (IAM role o `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`).
- Concurrencia de workers:
  - Edita `compose.worker.yml` (flag `--concurrency=`) y reinicia el servicio.
  - Ejemplos a probar: `--concurrency=1`, `2`, `4`.
- Almacenamiento:
  - Si usas S3: `STORAGE_BACKEND=s3`, `AWS_S3_BUCKET`, `S3_UPLOAD_PREFIX`, `S3_PROCESSED_PREFIX`.
  - Si usas filesystem: asegúrate que `UPLOAD_PATH` sea compartido y visible por el worker.

### Inyección directa a la cola (bypass web)
Usa el productor `load_tests/inject_worker_tasks.py`, que encola directamente tareas Celery hacia SQS con payloads realistas (rutas a archivo).

Comandos sugeridos:
```bash
# 1) Burst (saturación) - 50 MB
python load_tests/inject_worker_tasks.py --count 100 --size 50MB --mode burst --monitor

# 2) Burst (saturación) - 100 MB
python load_tests/inject_worker_tasks.py --count 50 --size 100MB --mode burst --monitor

# 3) Sustained (tasa fija) - 100 MB @ 10 tareas/min por 5 min
python load_tests/inject_worker_tasks.py --count 50 --size 100MB --mode sustained --rate 10 --monitor
```
Opcionales:
- `--file /ruta/o/s3://bucket/key.mp4` para reutilizar un archivo existente.
- `--user-id <id>` para asociar los videos a un usuario específico.

Salida:
- El script guarda los `task_id` en `load_tests/results/worker_tasks_YYYYMMDD_HHMMSS.log`.

### Matriz de pruebas
- Tamaños de video: 50 MB, 100 MB.
- Concurrencia de worker: 1, 2, 4 procesos/hilos por nodo.
- Para cada combinación ejecutar:
  - Prueba de saturación (burst).
  - Prueba sostenida (tasa fija que no sature).

### Monitoreo y observabilidad
- Logs del worker:
```bash
docker compose -f compose.worker.yml logs -f celery_worker
```
- Uso de recursos:
```bash
docker stats celery_worker
```
- Cola SQS (tamaño aproximado):
```bash
QUEUE_URL=$(aws sqs get-queue-url --queue-name "$SQS_QUEUE_NAME" --query 'QueueUrl' --output text)
aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```
  - `ApproximateNumberOfMessages`: mensajes esperando (cola visible).
  - `ApproximateNumberOfMessagesNotVisible`: en proceso (tomados por workers).

### Métricas y cálculos
- Throughput observado (X): videos completados por minuto en la ventana de la prueba.
- Tiempo medio de servicio (S): promedio de `(updated_at - uploaded_at)` por video (aproxima tiempo de ciclo; incluye espera mínima si la hubo).

Herramienta de cálculo:
```bash
python load_tests/compute_worker_metrics.py \
  --tasks-log load_tests/results/worker_tasks_YYYYMMDD_HHMMSS.log
```
Produce un resumen en consola y (opcionalmente) un CSV.

### Criterios de éxito/fallo
- Capacidad nominal: X (videos/min) por configuración.
- Estabilidad: en sostenido, la cola no debe crecer sin control (tendencia ~0).

### Tabla de resultados (ejemplo/plantilla)

| Tamaño | Concurrencia | Modo       | X (videos/min) | S promedio (s) | Notas                     |
|--------|--------------|------------|----------------|----------------|---------------------------|
| 50 MB  | 1            | Burst      |                |                |                           |
| 50 MB  | 2            | Burst      |                |                |                           |
| 50 MB  | 4            | Burst      |                |                |                           |
| 100 MB | 1            | Sustained  |                |                | tasa=10/min               |
| 100 MB | 2            | Sustained  |                |                | tasa=10/min               |
| 100 MB | 4            | Sustained  |                |                | tasa=10/min               |

### Puntos de saturación y cuellos de botella
Registrar hallazgos por configuración:
- CPU alta (worker)
- Decodificación/ffmpeg
- I/O de disco (temporal)
- Ancho de banda (S3/Red)

### Nombre del documento
Este documento se llama: `capacity-planning/escenario_2_worker_throughput.md`


