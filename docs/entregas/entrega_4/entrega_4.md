## Entrega 4 – Arquitectura Ajustada (Escalabilidad Web + Workers y Mensajería)
### Video 
[link video](https://drive.google.com/file/d/1j-CGG9F-0TJcAMkxYkkfptpUp249oXOp/view?usp=sharing)
### 1) Resumen
Se extiende la arquitectura de la entrega 3 para escalar no solo la capa web sino también la capa de procesamiento (workers), incorporando Amazon SQS como sistema de mensajería asíncrona entre la API y los workers. Se habilita alta disponibilidad en dos Zonas de Disponibilidad (Multi-AZ) para el balanceador y para los Auto Scaling Groups (ASG) de Web y Workers. El almacenamiento de originales/procesados permanece en Amazon S3 y la base de datos en Amazon RDS. Se estandarizan las instancias EC2 a 2 vCPU, 2 GiB de RAM y 30 GiB de almacenamiento por decisión de negocio.

### 2) Tecnologías y servicios incorporados
- Amazon EC2: ejecución de capa Web (Nginx + FastAPI) y capa Worker (Celery), 2 vCPU/2 GiB/30 GiB en t3.small.
- Amazon ALB (Load Balancer): distribución de tráfico HTTP/HTTPS hacia la capa Web (cross-zone enabled).
- Amazon Auto Scaling (ASG): escalamiento automático de Web y Workers (mín. 1, máx. 3).
- Amazon RDS (PostgreSQL): base de datos relacional administrada.
- Amazon S3: almacenamiento de videos originales y procesados.
- Amazon SQS: cola de mensajes (Standard) con DLQ para orquestar trabajos de procesamiento.
- Amazon CloudWatch: métricas, logs y alarmas para ALB, EC2, ASG, RDS y SQS.
- Nginx: reverse proxy hacia FastAPI y servido de estáticos si aplica.
- FastAPI: API REST de la aplicación.
- Celery: motor de tareas. Broker: SQS. Backend de resultados: Redis.
- Redis: backend de resultados de Celery (se mantiene para tracking de estados).

### 3) Cambios respecto a la entrega anterior
- Se agrega escalado automático de la capa Worker con políticas basadas en métricas de SQS (profundidad de cola y edad del mensaje más antiguo).
- Se adopta Amazon SQS como broker de Celery (antes, Redis cumplía rol de broker/backend). Redis queda como backend de resultados.
- Se habilita despliegue Multi-AZ para Web y Workers: ASGs distribuidos en al menos dos subredes privadas; ALB en subredes públicas de dos AZ.
- Se ajustan health-checks y warmup/cooldown de escalado según tiempos de arranque de la app y de los workers.
- Se consolidan AMIs de Web y Worker para arranque homogéneo en ASG Multi-AZ.

Variables/Parámetros operativos relevantes:
- STORAGE_BACKEND=s3
- CELERY_BROKER_URL=sqs:// (requiere credenciales AWS y permisos SQS)
- CELERY_RESULT_BACKEND=redis://HOST:PORT/DB
- AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- SQS_QUEUE_NAME, SQS_QUEUE_URL, SQS_DLQ_ARN, SQS_MAX_RECEIVE_COUNT=5
- SQS_LONG_POLL_SECONDS=20, SQS_VISIBILITY_TIMEOUT=2x tiempo máx. de tarea
- ASG_WEB_MIN=1, ASG_WEB_MAX=3; ASG_WORKER_MIN=1, ASG_WORKER_MAX=3
- ALB_HEALTHCHECK_PATH=/api/health, INTERVAL/THRESHOLDS ajustados

### 4) Modelo de despliegue (Deployment)

![Modelo de despliegue](../assets/entrega_4_d_despliegue.png)

Descripción breve:
- Usuarios → ALB (HTTP/HTTPS, cross-zone) → Nginx → FastAPI (capa Web).
- FastAPI escribe metadatos en RDS y publica mensajes en SQS con el trabajo a procesar.
- Workers (Celery) consumen de SQS, leen originales desde S3, procesan y publican resultados en S3; actualizan estado en RDS.
- ASG Web y ASG Worker distribuidos en dos AZ; mínimo 1, máximo 3 instancias cada uno.
- CloudWatch centraliza métricas y alarmas; SQS cuenta con DLQ para reintentos fallidos.

### 5) Modelo de componentes (Component)
Inserte aquí el diagrama de componentes:

![Modelo de componentes](../assets/entrega_4_d_componentes.png)

Componentes principales:
- ALB: escucha en :80/443, enruta al Target Group Web (Nginx/FastAPI).
- Capa Web: Nginx (reverse proxy) + FastAPI (API REST).
- Capa Worker: procesos Celery consumiendo desde SQS.
- SQS: cola Standard con DLQ (redrive policy configurada).
- Redis: backend de resultados de Celery.
- RDS (PostgreSQL): persistencia transaccional.
- S3: almacenamiento de originales y procesados.
- CloudWatch: métricas (ALB, EC2/ASG, RDS, SQS), logs y alarmas.

### 6) Balanceador de carga y alta disponibilidad (Multi-AZ) – 20%
- ALB aprovisionado en subredes públicas de dos AZ, con cross-zone load balancing habilitado.
- Target Group Web:
  - Protocolo/puerto: HTTP :80 (o HTTPS :443 detrás de Nginx).
  - Health check: `/api/health` (200 esperado, `{"status":"ok"}`), intervalo 15–30 s.
  - Sticky sessions: deshabilitadas (round-robin).
- ASG Web en subredes privadas de dos AZ, con distribución de instancias balanceada.

### 7) Autoscaling de la capa Web (recordatorio – ya implementado)
- ASG Web (Min=1, Max=3), políticas sugeridas:
  - TargetTracking: `ALBRequestCountPerTarget` (p. ej., 50 req/target).
  - Opcional: CPUUtilization p95 <-> 60–70% por más de N minutos.
  - Cooldown/warmup: 60–120 s, ajustable tras pruebas de carga.

### 8) Autoscaling de Workers (nuevo) – 20%
- ASG Worker (Min=1, Max=3) distribuido en dos AZ.
- Métricas de escalado (CloudWatch/SQS):
  - `ApproximateNumberOfMessagesVisible` (profundidad de cola).
- Consideraciones:
  - `SQS_VISIBILITY_TIMEOUT` ≥ 2x tiempo máx. de tarea para evitar reprocesos prematuros.
  - DLQ con `maxReceiveCount=5` para aislar mensajes problemáticos.

### 9) Mensajería asíncrona (SQS) – 20%
- Tipo de cola: Standard (alto throughput).
- Configuración:
  - DLQ (redrive policy) para mensajes que superen reintentos.
  - Política IAM mínima para que Web publique y Workers consuman/borran mensajes.
- Flujo:
  1) Web publica en SQS un payload con `video_id`, `s3_key_original`, `transformaciones`, `usuario_id`.
  2) Worker recibe y bloquea el mensaje (visibility timeout), descarga de S3, procesa (ffmpeg), sube a S3 `processed/`.
  3) Actualiza estado en RDS; confirma el mensaje (deleteMessage). Si falla, reintenta hasta DLQ.
- Celery:
  - Broker: `sqs://` (Kombu/boto3). Backend de resultados: Redis.
  - Concurrencia de workers ajustable según vCPU y perfil de IO.

### 10) Operación y despliegue
- AMIs de Web y Worker incluyen dependencias (Docker, docker-compose, ffmpeg, runtime).
- User-Data inicializa contenedores y registra la instancia en el ASG (via cloud-init).
- Variables de entorno desde SSM Parameter Store/Secrets Manager cuando aplica.
- Subredes: ALB en públicas; Web/Workers en privadas con egress vía NAT Gateway.
- Nginx mantiene `/api/health` para health-check y headers `X-Forwarded-*` desde ALB.

### 11) Observabilidad
- Logs de aplicación enviados a CloudWatch Logs;,trazas de errores clave con graphana, y scripts para el escenario 2.

### 12) Pruebas de carga y criterios de escalado
- Se ejecutan escenarios de carga para validar:
  - RPS objetivo por instancia Web y latencia p95 con ALB.
  - Profundidad de SQS y tiempo de clearing de cola con 1→3 workers.
- Ajustes recomendados tras mediciones:
  - Umbrales de scale-out/in según p95 y backlog promedio.
  - Warmup/cooldown conforme a tiempos reales de arranque.

