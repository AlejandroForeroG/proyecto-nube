## Entrega 5 – Pruebas de Carga y Análisis de Capacidad (ECS Fargate)

### 1) Objetivo

Evaluar la capacidad de la solución migrada a ECS Fargate, comparando tiempos de escalado, throughput y latencia con la arquitectura EC2 de la entrega anterior.

### 2) Alcance y entorno

- **Host bajo prueba (ALB)**: `http://alb-proyecto-nube-xxxx.us-east-1.elb.amazonaws.com:80`
- **Health-check**: `/api/health` (espera `{"status":"ok"}`)
- **Cómputo**:
  - Web: Fargate 0.5 vCPU / 1 GB (min 1, max 3 tareas)
  - Worker: Fargate 2 vCPU / 4 GB (min 1, max 4 tareas)
- **Base de datos**: Amazon RDS PostgreSQL
- **Almacenamiento**: Amazon S3 (`miso-proyecto-nube`)
- **Mensajería**: Amazon SQS (`cola-nube`)

### 3) Metodología

- **Herramienta**: Locust (headless y UI)
- **Métricas objetivo**:
  - p95 ≤ 1 s para capa web
  - Error rate ≤ 1%
  - Escalado out/in oportuno sin thrashing
- **Medición**:
  - Locust: req/s, latencias (avg, p50, p95, p99), errores
  - CloudWatch: ECS (CPUUtilization, MemoryUtilization), ALB (RequestCount, TargetResponseTime)
  - Container Insights: métricas de tareas Fargate

### 4) Escenario 1 – Capacidad de la capa Web

#### 4.1) Smoke Test – 5 usuarios

Se ejecutó una prueba de humo con 5 usuarios concurrentes para validar el funcionamiento básico del sistema.

**Resultados**:
- Las métricas se mantienen estables sin variaciones significativas
- Latencia promedio constante y baja
- CPU y memoria en niveles mínimos
- Sin errores detectados

![Smoke Test 5 usuarios](../assets/entrega_5/smoke_5.png)

#### 4.2) Ramp Test – 100 usuarios

Se ejecutaron pruebas de carga con **100 usuarios** durante **8 minutos** con un spawn rate de **0.55 usuarios/segundo**, lo que permite una escalabilidad gradual en aproximadamente 3 minutos.

**Configuración**:
```bash
locust -f load_tests/locustfile.py \
  -H http://alb-proyecto-nube-25892135.us-east-1.elb.amazonaws.com:80 \
  --headless --users 100 --spawn-rate 0.55 --run-time 8m \
  --html load_tests/results/100_users.html
```

**Resultados**:
- **Mejora significativa en latencia**: Mientras que en pruebas anteriores (EC2) la latencia se mantenía entre **15-20 segundos** después del cuello de botella, con ECS Fargate se mantiene entre **1.5-2 segundos**.
- **Escalado rápido**: Las tareas Fargate escalan en segundos vs. ~8 minutos en EC2.
- **CPU estable**: El uso de CPU muestra un comportamiento predecible durante el escalado.

**Evidencias de uso de CPU**:

![Ramp 100 usuarios - CPU 1](../assets/entrega_5/ramp_100.png)

![Ramp 100 usuarios - CPU 2](../assets/entrega_5/ramp_100_2.png)

**Evidencias de latencia y métricas**:

![Ramp 100 usuarios - Latencia](../assets/entrega_5/ramp_100_latency.png)

![Ramp 100 usuarios - Tabla](../assets/entrega_5/ramp_100_table.png)

#### 4.3) Sustained Test – 64 usuarios (80% del punto de quiebre)

Se identificó el **punto de quiebre en 80 usuarios concurrentes**. Aplicando el factor de seguridad del 80%, se obtienen **64 usuarios** como carga sostenible óptima.

**Configuración**:
```bash
locust -f load_tests/locustfile.py \
  -H http://alb-proyecto-nube-25892135.us-east-1.elb.amazonaws.com>:80 \
  --headless --users 64 --spawn-rate 0.35 --run-time 10m \
  --html load_tests/results/64_users.html
```

**Resultados**:
- **Capacidad duplicada**: 64 usuarios concurrentes representa casi el **doble** de la capacidad soportada con la arquitectura EC2 anterior (~35-40 usuarios).
- **Latencia baja y estable**: Se mantiene alrededor de **800 ms** en promedio.
- **CPU balanceada**: El uso de CPU se mantiene entre **45-50%** entre los servicios, dejando margen para picos.

**Evidencias de latencia y métricas**:

![Sustained 64 usuarios - Latencia](../assets/entrega_5/sustanined_64_users_latency.png)

![Sustained 64 usuarios - Tabla](../assets/entrega_5/sustaniner_64_user_table.png)

**Evidencias de uso de CPU**:

![Sustained 64 usuarios - CPU 1](../assets/entrega_5/64_ramp.png)

![Sustained 64 usuarios - CPU 2](../assets/entrega_5/64_ramp_2.png)

#### 4.4) Conclusiones y recomendaciones

##### Análisis técnico

La migración de EC2 a ECS Fargate demuestra mejoras sustanciales en el rendimiento y la capacidad de respuesta del sistema:

1. **Reducción drástica en tiempos de despliegue**: El tiempo de escalado se reduce de **~10 minutos** (bootstrap de instancias EC2) a **menos de 1 minuto** (pull de imagen y arranque de contenedor). Esto elimina el cuello de botella identificado en entregas anteriores, donde el tiempo de despliegue de instancias afectaba la latencia durante eventos de scale-out.

2. **Mejora en latencia bajo carga**: La latencia p95 durante pruebas de carga se reduce de **15-20 segundos** (EC2) a **1.5-2 segundos** (Fargate), representando una mejora de **~10x**.

3. **Mayor capacidad sostenible**: El sistema ahora soporta **64 usuarios concurrentes** con latencia aceptable (~800 ms p95), comparado con **~35-40 usuarios** en la arquitectura anterior. Esto representa un incremento de **~60-80%** en capacidad.

##### Limitaciones identificadas

- **Punto de quiebre**: 80 usuarios concurrentes con uso de CPU cercano al **90%** en las 3 tareas máximas configuradas por la política de autoscaling.
- **Capacidad nominal recomendada**: 64 usuarios concurrentes (80% del punto de quiebre) con latencia p95 de **~800 ms**.

##### Recomendaciones para escalar más allá de 80 usuarios

| Opción | Descripción | Impacto estimado |
|--------|-------------|------------------|
| **Aumentar max tasks** | Incrementar `maxCapacity` de 3 a 5-6 tareas en la política de autoscaling | +60-100% capacidad |
| **Escalar verticalmente** | Aumentar CPU/memoria por tarea (ej. 1 vCPU / 2 GB) | +50-80% throughput por tarea |
| **Optimizar aplicación** | Profiling de endpoints lentos, connection pooling, caching | +20-40% eficiencia |
| **Ajustar workers Gunicorn** | Incrementar workers de Uvicorn según vCPUs disponibles | +10-30% throughput |
| **Implementar caching** | Redis/ElastiCache para respuestas frecuentes | Reducción de carga en DB |
| **Revisar queries DB** | Índices, optimización de consultas, read replicas | Reducción de latencia DB |

### 5) Escenario 2 – Throughput de Workers

<!-- Completar con resultados de pruebas de procesamiento de video -->

### 6) Conclusiones generales

<!-- Completar con conclusiones finales -->

