## Entrega 3 – Pruebas de Carga y Análisis de Capacidad

### 1) Objetivo
Evaluar la capacidad de la solución tras incorporar ALB + ASG en la capa web, y dejar evidencia de métricas clave (latencia, throughput, errores) y eventos de escalamiento automático.

### 2) Alcance y entorno
- Host bajo prueba (ELB): `http://ELB-151838069.us-east-1.elb.amazonaws.com:80`
- Health-check: `/api/health` (espera `{"status":"ok"}`)
- Instancias (laboratorio): t3.micro (ajustable según resultados)
- Límite ASG capa web: máx. 3 instancias
- Base de datos: RDS PostgreSQL (o EC2 en fases iniciales)
- Almacenamiento de objetos: Amazon S3 (originales y procesados)

### 3) Metodología
- Herramienta: Locust (UI y headless)
- Métricas objetivo (referenciales, ajustar por SLOs del equipo):
  - p95 <= 1 s (Escenario 1), errores<= 1–5%
  - Escalado out/in oportuno (sin thrashing) bajo picos de carga
- Medición:
  - Locust: req/s, latencias, errores
  - CloudWatch: ALB (RequestCount, TargetResponseTime), EC2 (CPU), eventos ASG
  - Opcional: Prometheus/Grafana si se habilitan exporters

### 4) Escenario 1 – Capacidad de la capa web
- Propósito: Medir throughput/latencia del plano web sin procesamiento de fondo.
- Endpoint: `GET /api/health`
- Criterios a observar:
  - p95/avg de respuesta
  - Error rate
  - RequestCount por target y tiempos de respuesta (ALB)
  - Activaciones del ASG (escalado out/in) y estabilización

Ejemplo (headless, escalado por pasos, 10 min):

```bash
locust -f load_tests/locustfile.py \
  -H http://ELB-151838069.us-east-1.elb.amazonaws.com:80 \
  --headless --users 200 --spawn-rate 20 --run-time 10m \
  --step-load --step-users 50 --step-time 2m \
  --html load_tests/results/health_report.html --csv load_tests/results/health
```

Locustfile de ejemplo (básico):

```python
from locust import HttpUser, task, between

class HealthUser(HttpUser):
    wait_time = between(0.2, 1.0)
    @task
    def health(self):
        with self.client.get("/api/health", name="/api/health", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"Bad status: {r.status_code}")
            else:
                try:
                    if r.json().get("status") != "ok":
                        r.failure(f"Unexpected body: {r.text}")
                except Exception:
                    r.failure("Invalid JSON")
```


### 5) Resultados y análisis
- Configuración (borrador; completar con fechas/commits/tamaños exactos):
  - Instancias t3.micro, ASG máx. 3 instancias, ALB con HC `/api/health`.
  - Cargas por pasos con Locust (UI y headless), ramp-up y pruebas sostenidas.
- Escenario 1 (mock/health):
  - Resultados muy similares entre corridas; se evidenció que el tiempo de despliegue de nuevas instancias puede demorar hasta ~8 minutos, afectando la estabilización de métricas durante escalado.
  - Con políticas iniciales el sistema se “rompía” alrededor de 50 usuarios concurrentes. Ajustando el umbral (p. ej., objetivo 80 req/target en TargetTracking), la plataforma estabilizaba cerca de ~40 usuarios. Se realizaron pruebas focalizadas con 38 usuarios para evaluar estabilidad.
  - A pesar de que las gráficas muestran variaciones amplias en el tiempo de respuesta durante el warm-up/escala, los promedios reportados por Locust mejoraron; la p95 quedó con variabilidad durante los eventos de scale-out.
- Escenario 2 (fin a fin con workers):
  - Patrones similares: métricas agregadas cercanas entre corridas, con diferencias apreciables en picos según el momento en que el ASG agrega/quita instancias y el worker toma carga.
  - En la prueba con 38 usuarios se observaron resultados más constantes, con picos más altos pero menor dispersión entre ventanas, sugiriendo impacto del warm-up de instancias.
- Gráficas/tablas (adjuntar):
  - Locust HTML: `load_tests/results/health_report.html`
  - CSVs: `load_tests/results/health_*`
  - CloudWatch: capturas de RequestCount, TargetResponseTime, CPU, actividad del ASG
  - Evidencias
    - [Ramp 100 usuarios](../assets/semana_3_ramp_100.png)
    - [Ramp 100 usuarios (variante 2)](../assets/semana_3_ramp_100_2.png)
    - [Sustained 40 usuarios](../assets/semana_3_sustained_40_users.png)
    - [Sustained 40 usuarios (variante 2)](../assets/semana_3_sustaned_40_users_2.png)
    - [Smoke test – evidencia](../assets/semana3_evidencia_smoke.png)

### 6) Observaciones de escalamiento
- Hipótesis principal: el tiempo de arranque/configuración de instancias (bootstrap, instalación/montaje de librerías/paquetes) durante el scale-out impacta la latencia percibida hasta estabilizarse; esto coincide con demoras cercanas a ~8 minutos en ciertos despliegues.
- Umbral de activación: con ajuste de objetivo a ~80 req/target se observó estabilización alrededor de 40 usuarios; por encima de ~50 usuarios se observaron degradaciones si el scale-out no completaba el warm-up a tiempo.
- Warm-up/estabilización: ventana prolongada hasta que las instancias nuevas entran sanas al Target Group; durante ese periodo aumenta la p95 y la variabilidad.
- Thrashing: no se observó bucle rápido de scale-in/out, pero hay riesgo si los cooldowns son cortos frente al tiempo real de warm-up.
- Costos vs performance: al mantener t3.micro y máx. 3 instancias, el costo se mantiene bajo, pero la p95 durante escala muestra sensibilidad al tiempo de bootstrap.

### 7x) Conclusiones y recomendaciones
- Reducir impacto de warm-up:
  - Usar AMIs pre-horneadas con dependencias (Docker, imágenes, ffmpeg) y user-data mínimo.
  - Aumentar `warmup`/`cooldown` en políticas de Auto Scaling acorde al tiempo real de arranque.
- Ajustar política de escalado:
  - Evaluar TargetTracking por `ALBRequestCountPerTarget` vs CPU y calibrar objetivo (p. ej., 60–80 req/target) según p95 deseada.
  - Considerar `maxCapacity` > 3 si los SLOs lo requieren y el costo lo permite.
- Tamaño de instancia:
  - Escalar a t3.small/t3.medium si la p95 sigue por encima del objetivo aun con warm-up mitigado.
- Optimización de plano web:
  - Revisar keep-alive, workers de Uvicorn/Gunicorn, y afinamiento de Nginx/timeout del ALB.
- Backend y almacenamiento:
  - Para cargas de subida grandes, usar multipart en S3 y verificar límites de Nginx/ALB.
  - En DB, considerar pgbouncer y límites de conexiones en RDS.





