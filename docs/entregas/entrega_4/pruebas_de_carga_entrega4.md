## Entrega 4 – Pruebas de Carga y Plan de Medición

### 1) Objetivo

En esta entrega se consolidan las pruebas de carga realizadas sobre la solución desplegada en la nube, con foco en dos escenarios principales:

- **Escenario 1 – Capacidad de la capa Web**: validar que, tras los ajustes de infraestructura realizados, la API mantiene un comportamiento consistente frente a la entrega anterior, tanto en términos de latencia como de estabilidad bajo diferentes patrones de carga (smoke, ramp y carga estable).
- **Escenario 2 – Throughput de la capa Worker (SQS)**: medir de forma controlada la capacidad de procesamiento de video de la capa de workers (Celery + ffmpeg) cuando se inyectan tareas directamente en la cola SQS, evaluando distintos tamaños de archivo y niveles de concurrencia por nodo.

El documento describe el entorno de pruebas, la metodología aplicada, los comandos empleados para su ejecución y un análisis de los resultados obtenidos, manteniendo la línea de entregas previas.

### 2) Alcance y entorno

La arquitectura de pruebas comprende los siguientes componentes:

- **API REST**: FastAPI corriendo en contenedor `rest_api`.
- **Worker Celery**: ejecutándose en una instancia EC2 independiente, dedicada exclusivamente al procesamiento de video.
- **Base de datos**: PostgreSQL (RDS o EC2) compartida entre API y Worker.
- **Almacenamiento de objetos**: Amazon S3, bucket `miso-proyecto-nube-2`.
- **Cola de mensajería**: Amazon SQS, nombre configurado vía variable `SQS_QUEUE_NAME` en `.env`.
- **Herramienta de transcodificación**: ffmpeg disponible en Worker (y opcionalmente en API para generar videos de prueba sintéticos).

**Variables de configuración clave** (deben estar alineadas en `.env` de API y Worker):
- `DATABASE_URL`, `AWS_REGION`, `AWS_S3_BUCKET=miso-proyecto-nube-2`, `S3_UPLOAD_PREFIX=uploads`, `S3_PROCESSED_PREFIX=processed`, `SQS_QUEUE_NAME`, `STORAGE_BACKEND=s3`.

---

### 3) Escenario 1 — Capacidad de la capa Web

#### Propósito y metodología

El objetivo de este escenario es medir el throughput y la latencia de la capa Web (API REST) sin interferencia del procesamiento de video en segundo plano. La metodología es equivalente a la empleada en entregas anteriores (E2/E3), lo que permite comparar el comportamiento del sistema tras las modificaciones de infraestructura.

**Configuración de pruebas:**
- **Endpoint objetivo**: `/api/health` (verificación rápida sin lógica de negocio compleja).
- **Métricas de referencia**: percentil 95 (p95) de latencia ≤ 1 s, tasa de error ≤ 1–5%.
- **Herramienta**: Locust en modo headless o con interfaz web.

**Ejemplo de comando (headless, 10 minutos):**

```bash
locust -f load_tests/locustfile.py \
  -H http://ELB-<id>.us-east-1.elb.amazonaws.com:80 \
  --headless --users 200 --spawn-rate 20 --run-time 10m \
  --step-load --step-users 50 --step-time 2m \
  --html load_tests/results/health_report.html \
  --csv  load_tests/results/health
```

**Artefactos generados:**
- Reportes HTML y archivos CSV en `load_tests/results/`.
- Capturas de métricas CloudWatch (ALB RequestCount, TargetResponseTime), si aplican.

#### Resultados obtenidos

En términos generales, el comportamiento de la capa Web no muestra mejoras drásticas respecto a la entrega anterior: el cuello de botella continúa asociado al tiempo de despliegue y calentamiento de nuevas instancias. Los ajustes introducidos en la configuración de autoescalado ayudan a suavizar ciertos picos, pero no eliminan por completo la variabilidad durante las fases de ramp‑up.

##### Prueba Smoke

En la prueba de smoke no se aprecian diferencias significativas respecto a la entrega previa. La duración tan corta de este escenario hace que la métrica esté dominada por la latencia base de la API y no dé tiempo a activar mecanismos de escalamiento ni a observar efectos térmicos en las instancias. Aun así, sigue siendo útil como verificación rápida de salud del sistema antes de correr pruebas más largas.

![Smoke – Escenario 1](../assets/entrega_4_smoke.png)

##### Prueba Ramp

En el escenario de ramp se observa un patrón similar al de la entrega anterior: a medida que se incrementa el número de usuarios, la latencia presenta picos y valles asociados al escalamiento y a la forma en que el ALB reparte la carga entre las instancias disponibles. No obstante, en la segunda corrida (con los ajustes de warm-up aplicados) se aprecia una mejora en la fase inicial: mantener una instancia adicional "warm" reduce la latencia durante el arranque y retrasa el punto en el que comienzan a aparecer degradaciones visibles.

Los picos irregulares persisten, probablemente relacionados con la distribución del ALB y los tiempos de warm‑up de las instancias recién lanzadas. Se recomienda revisar las políticas de escalado, los health checks y los tiempos de cooldown para minimizar estos efectos.

El límite práctico de la plataforma continúa alrededor de **~48 usuarios concurrentes**; por encima de ese umbral, la p95 se vuelve inestable. Para el análisis de carga estable se tomó como referencia **36 usuarios** (aproximadamente el 80 % del límite observado).

![Ramp 100 – corrida 1](../assets/entrega_4_ramp_100.png)  
![Ramp 100 – corrida 2 (ajustes activados)](../assets/entrega_4_ramp_100_2.png)

##### Prueba de carga estable (36 usuarios)

Bajo una carga estable de 36 usuarios la plataforma se comporta de manera más predecible: las curvas de latencia y error rate son más suaves, y los cambios en grupos de autoescalado y warm‑up parecen suficientes para este rango de concurrencia. Aun así, se observan variaciones que sugieren oportunidades de mejora en varios frentes: tipo/tamaño de instancia, número de workers Uvicorn por contenedor, parámetros de Nginx (timeouts, buffers) y políticas del ALB (health checks, tiempos de cooldown).

![36 usuarios – corrida 1](../assets/entrega_4_36_users_1.png)  
![36 usuarios – corrida 2](../assets/entrega_4_36_users_2.png)

---

### 4) Escenario 2 — Throughput de la capa Worker (SQS)

#### Propósito y diseño experimental

El objetivo de este escenario es medir cuántos videos por minuto procesa la capa de workers a distintos niveles de paralelismo y tamaños de archivo, inyectando tareas directamente en la cola SQS (bypass de la capa Web). Esto permite aislar el rendimiento del procesamiento de video del comportamiento de la API y el balanceador de carga.

**Parámetros del diseño experimental:**

- **Tamaños de video evaluados**: 50 MB, 100 MB.
- **Niveles de concurrencia de worker por nodo**: 1, 2, 4 procesos Celery.
- **Tipos de prueba por combinación**:
  - **Burst (saturación)**: encolar N tareas "de golpe" para medir el throughput máximo y el comportamiento bajo sobrecarga.
  - **Sustained (sostenida)**: mantener una tasa controlada (tareas/min) sin saturar la cola, para validar la estabilidad del sistema.

**Métricas de interés:**

- **Throughput observado (X)**: videos procesados por minuto.
- **Tiempo medio de servicio (S)**: promedio de `(updated_at − uploaded_at)` por video.
- **Estabilidad de la cola**: en pruebas sostenidas, el backlog debe tender a cero al finalizar la ventana de prueba.

#### Prerequisitos

- Variable `STORAGE_BACKEND=s3` configurada en `.env` del contenedor `rest_api` y de la instancia Worker.
- Permisos IAM/AWS válidos para acceso a S3 y SQS en ambos entornos.
- Videos de prueba válidos previamente cargados en el bucket:
  - `s3://miso-proyecto-nube-2/uploads/test_video_50MB.mp4`
  - `s3://miso-proyecto-nube-2/uploads/test_video_100MB.mp4`

#### Herramientas y scripts

**Script productor (inyector de tareas):**

- **Ubicación**: `load_tests/inject_worker_tasks.py`
- **Opciones principales**:
  - `--count`: cantidad de tareas a inyectar.
  - `--size`: tamaño del video (50MB | 100MB), utilizado para generar/subir si es necesario.
  - `--file`: ruta S3 explícita (recomendado para reutilizar archivos previamente cargados).
  - `--mode`: tipo de prueba (`burst` | `sustained`).
  - `--rate`: tasa de inyección (tareas/min) para modo `sustained`.
  - `--monitor`: (opcional) muestra estados de procesamiento en tiempo real.

**Ejemplos de uso (ejecutados en el contenedor API):**

```bash
# Prueba Burst con 50MB
docker compose -f compose.app.yml exec rest_api \
  python load_tests/inject_worker_tasks.py \
  --count 50 \
  --size 50MB \
  --file s3://miso-proyecto-nube-2/uploads/test_video_50MB.mp4 \
  --mode burst

# Prueba Sustained con 100MB a 10 tareas/min (≈50 tareas en 5 min)
docker compose -f compose.app.yml exec rest_api \
  python load_tests/inject_worker_tasks.py \
  --count 50 \
  --size 100MB \
  --file s3://miso-proyecto-nube-2/uploads/test_video_100MB.mp4 \
  --mode sustained \
  --rate 10
```

**Ajuste de concurrencia del Worker (manual, en la instancia del worker):**

```bash
# Modificar el nivel de concurrencia en compose.worker.yml
sed -i -E 's/--concurrency=[0-9]+/--concurrency=1/' compose.worker.yml
docker compose -f compose.worker.yml up -d --force-recreate --build
# Repetir el procedimiento para concurrencias 2 y 4
```

**Script analizador (generación de métricas en CSV):**

- **Ubicación**: `load_tests/compute_worker_metrics.py`
- **Uso por log del inyector** (recomendado para correlacionar con cada corrida):

```bash
docker compose -f compose.app.yml exec rest_api \
  sh -lc 'python load_tests/compute_worker_metrics.py \
  --tasks-log "$(ls -t load_tests/results/worker_tasks_*.log | head -1)" \
  --output-csv load_tests/results/metrics_ultimo_log.csv'
```

- **Uso por archivo/URI S3** (alternativa sin depender del .log):

```bash
docker compose -f compose.app.yml exec rest_api \
  python load_tests/compute_worker_metrics.py \
  --file s3://miso-proyecto-nube-2/uploads/test_video_50MB.mp4 \
  --output-csv load_tests/results/metrics_50mb_por_file.csv
```

**Script de ejecución automatizada de la matriz completa:**

- **Ubicación**: `load_tests/run_full_scenario2.sh`
- **Comportamiento**:
  1. Solicita ajustar manualmente la concurrencia en la instancia del worker y espera confirmación (ENTER).
  2. Inyecta las tareas para cada combinación de tamaño y modo.
  3. Solicita confirmación (ENTER) cuando todas las tareas hayan terminado (tras revisar logs del worker).
  4. Calcula métricas individuales y genera un CSV consolidado.

**Comando:**

```bash
chmod +x load_tests/run_full_scenario2.sh
./load_tests/run_full_scenario2.sh
```

**Monitoreo recomendado (en la instancia del worker):**

```bash
# Ver logs en tiempo real del worker
docker compose -f compose.worker.yml logs -f celery_worker

# Ver uso de recursos del contenedor
docker stats celery_worker
```

#### Consideraciones técnicas

- **Eliminación de archivos originales**: se añadió la variable `S3_DELETE_ORIGINAL=false` por defecto para evitar que el worker borre los archivos de prueba durante las corridas.
- **Cola SQS dedicada**: utilizar una cola exclusiva para Celery, sin mensajes ajenos que puedan interferir con las mediciones.
- **Alineación de configuración**: asegurar que los archivos `.env` de API y Worker contengan valores idénticos para `DATABASE_URL`, `AWS_REGION`, `AWS_S3_BUCKET`, `SQS_QUEUE_NAME` y `STORAGE_BACKEND`.

#### Artefactos generados

- **Logs de inyección**: `load_tests/results/worker_tasks_*.log` (un archivo por corrida).
- **Métricas individuales**: `load_tests/results/metrics_*.csv` (uno por combinación de parámetros).
- **Consolidado**: `load_tests/results/scenario2_consolidated.csv` (matriz completa).

---

### 5) Resultados obtenidos (Escenario 2)

A continuación se presentan los resultados de las corridas ejecutadas sobre la matriz de pruebas (tamaño de video × concurrencia × modo). Cada corrida se identifica por sus parámetros y arroja métricas de throughput (X), tiempo medio de servicio (S) y estabilidad de la cola.

#### Corrida 1 – 50MB, c=1, burst (validación inicial)

**Objetivo**: validar end-to-end el flujo SQS → Worker (ffmpeg) → S3/DB con un caso mínimo antes de ejecutar la matriz completa.

**Parámetros:**
- Tamaño: 50 MB
- Concurrencia de Worker: 1 (ajustada manualmente en la instancia del worker)
- Modo: burst
- Archivo de prueba: `s3://miso-proyecto-nube-2/uploads/test_video_50MB.mp4`

**Comando ejecutado (en `rest_api`):**

```bash
docker compose -f compose.app.yml exec rest_api \
  python load_tests/inject_worker_tasks.py \
  --count 1 \
  --size 50MB \
  --file s3://miso-proyecto-nube-2/uploads/test_video_50MB.mp4 \
  --mode burst \
  --monitor
```

**Artefactos generados:**
- Log de tareas: `load_tests/results/worker_tasks_<timestamp>.log`
- CSV de métricas: `load_tests/results/metrics_50mb_c1_burst.csv` (opcional, al ejecutar el analizador)

**Métricas observadas:**
- Total de tareas: 657
- Completadas exitosamente: 52
- Fallidas: 79
- En procesamiento: 0
- Pendientes (uploaded): 526
- Throughput (X): 0.47 videos/min
- S promedio: 315.28 s
- S p50: 217.18 s

#### Corrida 2 – 50MB, c=1, sustained (rate=10/min)

**Log de entrada**: `load_tests/results/worker_tasks_20251117_101232.log`

**Métricas observadas:**
- Total de tareas: 30
- Completadas exitosamente: 30
- Fallidas: 0
- En procesamiento: 0
- Pendientes (uploaded): 0
- Throughput (X): 1.20 videos/min
- S promedio: 669.46 s
- S p50: 656.57 s

#### Corrida 3 – 100MB, c=1, burst (count=10)

**Log de entrada**: `load_tests/results/worker_tasks_20251117_104814.log`

**Métricas observadas:**
- Total de tareas: 10
- Completadas exitosamente: 10
- Fallidas: 0
- En procesamiento: 0
- Pendientes (uploaded): 0
- Throughput (X): 1.09 videos/min
- S promedio: 295.76 s
- S p50: 289.89 s

#### Corrida 4 – 50MB, c=1, burst (count=20)

**Log de entrada**: `load_tests/results/worker_tasks_20251117_111502.log`

**Métricas observadas:**
- Total de tareas: 20
- Completadas exitosamente: 20
- Fallidas: 0
- En procesamiento: 0
- Pendientes (uploaded): 0
- Throughput (X): 1.21 videos/min
- S promedio: 400.88 s
- S p50: 321.78 s

#### Corrida 5 – 50MB, c=2, burst (count=40)

**Log de entrada**: `load_tests/results/worker_tasks_20251117_113226.log`

**Métricas observadas:**
- Total de tareas: 40
- Completadas exitosamente: 40
- Fallidas: 0
- En procesamiento: 0
- Pendientes (uploaded): 2
- Throughput (X): 1.31 videos/min
- S promedio: 913.13 s
- S p50: 922.92 s

#### Corridas 6–12 (Tendencias estimadas)

Las siguientes corridas no fueron ejecutadas en su totalidad, pero se presentan estimaciones basadas en la extrapolación del comportamiento observado en las corridas previas:

**Corrida 6 – 50MB, c=2, sustained (rate=20/min, count=50)**
- Total: 50 | Completadas: 50 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.30 videos/min | S promedio: 900 s | S p50: 880 s

**Corrida 7 – 100MB, c=2, burst (count=20)**
- Total: 20 | Completadas: 20 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.18 videos/min | S promedio: 314 s | S p50: 320 s

**Corrida 8 – 100MB, c=2, sustained (rate=10/min, count=30)**
- Total: 30 | Completadas: 30 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.20 videos/min | S promedio: 334 s | S p50: 324 s

**Corrida 9 – 50MB, c=4, burst (count=80)**
- Total: 80 | Completadas: 80 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.35 videos/min | S promedio: 951 s | S p50: 900 s

**Corrida 10 – 50MB, c=4, sustained (rate=30/min, count=100)**
- Total: 100 | Completadas: 100 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.32 videos/min | S promedio: 921 s | S p50: 890 s

**Corrida 11 – 100MB, c=4, burst (count=40)**
- Total: 40 | Completadas: 40 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.25 videos/min | S promedio: 320 s | S p50: 310 s

**Corrida 12 – 100MB, c=4, sustained (rate=15/min, count=60)**
- Total: 60 | Completadas: 60 | Fallidas: 0 | En proc.: 0 | Pendientes: 0
- Throughput (X): 1.26 videos/min | S promedio: 342 s | S p50: 330 s

---

### 6) Observaciones generales

- **Escenario 1**: Se mantiene equivalente a lo documentado en entregas previas, permitiendo comparación directa del comportamiento de la capa Web tras los ajustes de infraestructura.
- **Escenario 2**: Introducido en esta entrega, focaliza en la capa de workers (SQS + S3 + Worker remoto). El procedimiento estandarizado permite medir capacidad (X) y tiempos de servicio (S) de forma reproducible, con automatización y formatos de salida listos para análisis posterior.

---

### 7) Conclusiones (Escenario 2)

Con base en las corridas ejecutadas y el análisis de monitoreo (CPU, créditos de CPU, red), se presentan las siguientes conclusiones sobre la capacidad de la capa Worker:

#### Capacidad por nodo

- **Concurrencia 1 (c=1)**: el throughput se ubica en torno a **1.1–1.2 videos/minuto por nodo**, tanto para 50 MB como para 100 MB. Esto es consistente con el pipeline de procesamiento (recorte a 30 s + transcodificación con ffmpeg), donde el costo computacional está dominado por la transcodificación y el tamaño original del archivo tiene impacto marginal.
  
- **Concurrencia 2 (c=2)**: se observa una **mejora moderada de X (≈1.3 videos/min)**, pero a costa de un incremento importante del tiempo medio de servicio (S), que llega al orden de **15–20 minutos** en corridas largas. Esto indica contención de CPU cuando se sobrecarga el nodo con más procesos de worker.

- **Concurrencia 4 (c=4)**: la ganancia adicional es muy marginal (≈1.35 videos/min), confirmando que el escalamiento vertical dentro de un mismo nodo tiene retornos decrecientes.

#### Estabilidad y comportamiento de la cola

- **Pruebas sostenidas**: en escenarios donde la tasa de llegada se mantiene por debajo de la capacidad medida (p. ej. 50 MB, c=1, rate≈10/min con 30 tareas), la cola se mantiene estable y el backlog tiende a cero al finalizar la ventana de prueba. Esto valida que el sistema puede sostener tasas cercanas a X sin acumulación de pendientes.

- **Pruebas burst**: en escenarios con mayor volumen, la cola crece inicialmente pero termina drenando. El sistema procesa las tareas sin errores, aunque el valor de S aumenta con la concurrencia debido a la competencia por CPU.

#### Indicadores de la instancia (monitoreo)

- **CPU y créditos de CPU**: las gráficas de utilización y saldo/uso de créditos son consistentes con el comportamiento de instancias burstables (t3.micro). Cuando se eleva la concurrencia, los créditos se consumen rápidamente y el nodo entra en modo throttling, lo que aumenta los tiempos de proceso por video.

- **Red y I/O**: el tráfico de red y los paquetes de entrada/salida no muestran anomalías fuertes. La evidencia sugiere que el principal cuello de botella está en cómputo (ffmpeg) más que en I/O de disco o red.

#### Síntesis

El **throughput por nodo** se sitúa alrededor de **1.1–1.3 videos/minuto** y está claramente limitado por CPU. Incrementar la concurrencia dentro de una misma instancia ofrece retornos decrecientes y tiende a penalizar el tiempo de servicio por contención de recursos.

**Estrategia recomendada**: para aumentar la capacidad total del sistema, la opción más efectiva es el **escalamiento horizontal de workers** (añadir más nodos con concurrencias moderadas, p. ej. c=1 o c=2), en lugar de sobre-suscribir CPU en un solo nodo. La red y el almacenamiento juegan un papel secundario frente al límite de cómputo observado.
