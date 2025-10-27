## Entrega 2 – Documentación de Arquitectura Ajustada

### 1) Resumen
Se implementó un despliegue distribuido en AWS compuesto por tres instancias Amazon EC2: Web Server (API + Nginx), Worker (Celery) y File Server (NFS), junto con una base de datos gestionada en Amazon RDS (PostgreSQL). El objetivo es desacoplar responsabilidades, permitir escalamiento independiente y compartir archivos entre componentes mediante NFS v4.1.

### 2) Tecnologías y servicios incorporados
- FastAPI: Backend de la aplicación web (API REST) y servidor de archivos procesados vía Nginx.
- Celery: Procesamiento asíncrono de tareas de video (recorte, escalado, watermark, etc.).
- Redis: Broker/backend de Celery.
- Nginx: Reverse proxy y servido de estáticos procesados.
- Amazon EC2: Infraestructura de cómputo para Web Server, Worker y File Server (NFS).
- Amazon RDS (PostgreSQL): Base de datos relacional gestionada.
- NFS v4.1: Sistema de archivos compartido entre Web Server y Worker para `uploads/` y `processed/` (servido por File Server).
- Docker + Docker Compose: Orquestación por instancia (archivos en `docker/`).
- Scripts de automatización: `scripts/aws-setup.sh`, `scripts/nfs-server-mount.sh`, `scripts/nfs-client-mount.sh`, `scripts/nfs-client-unmount.sh`.
 - Observabilidad: Prometheus, Grafana y Node Exporter (para métricas y paneles de monitoreo).

Instancias EC2 (decisión de negocio): 2 vCPU, 2 GiB RAM, 50 GiB de almacenamiento por instancia.

### 3) Cambios respecto a la entrega anterior
- Separación de componentes en 3 instancias EC2 (antes, colocalizados):
  - Web Server: `rest_api` (FastAPI), `nginx`, `prometheus`, `node-exporter`, `grafana`.
  - Worker: `celery_worker`, `redis`.
  - File Server: contenedor NFS (exporta `/exports` mapeado a `/srv/nfs`).
- Desacople del `docker-compose` principal en múltiples archivos dentro de `docker/`:
  - `compose.app.yml`, `compose.worker.yml`, `compose.file-server.yml`, `compose.db.yml`, `compose.local.yml`.
- Core Storage (`app/core/storage.py`):
  - Creación de `NFSStore` para escritura segura en NFS (forzado `fsync()` tras escribir).
  - Incorporación de `get_storage(storage_backend)` para seleccionar el backend de almacenamiento según variable indicada (manteniendo `LocalStorage` para entorno local).
- API de Videos (`app/api/routes/videos.py`):
  - Refactor para usar `get_storage(...)` en lugar de acoplarse a `LocalStorage` directamente.
- Nginx (`nginx/nginx.conf`):
  - Ajustes para despliegue en AWS (cabeceras `X-Forwarded-*`, rutas de estáticos `processed/`, proxy a la API).
- Incorporación de NFS v4.1 como sistema de archivos compartido para `uploads/` y `processed/` entre Web Server y Worker.
- Uso de Amazon RDS para la base de datos relacional (PostgreSQL) gestionada.
- Automatización de bootstrap y montaje NFS mediante scripts y flag `--nfs-role` en `aws-setup.sh`.

### 4) Modelo de despliegue (Deployment)

[Ver imagen del diagrama](../assets/entrega_2_d_despliegue.png)

Descripción:
- VPC privada con subredes donde residen tres instancias EC2: Web Server, Worker y File Server.
- Security Groups limitan acceso:
  - Web Server: expone HTTP/HTTPS (80/443) público; acceso interno a Redis si se usa localmente.
  - Worker: sin puertos públicos; acceso interno a Redis y a Web Server si aplica; accede al NFS.
  - File Server: expone NFS (2049/TCP) solo a Web Server y Worker.
- Amazon RDS (PostgreSQL) accesible desde Web Server y Worker por SG internos.

- Grupo de Seguridad único (SG) – Reglas de entrada:
  - HTTP 809/TCP
  - HTTPS 443/TCP
  - SSH 22/TCP
  - PostgreSQL 5432/TCP
  - NFS 2049/TCP
  - Redis 6379/TCP

### 5) Modelo de componentes (Component)

[Ver imagen del diagrama](../assets/entrega_2_d_componentes.png)

Componentes principales:
- API (FastAPI):
  - Endpoints de autenticación y manejo de videos (`/api/videos/*`).
  - Escribe originales en `UPLOAD_PATH` y expone procesados vía Nginx.
- Celery Worker:
  - Consume tareas desde Redis.
  - Lee originales desde NFS y escribe procesados en NFS (`PROCESSED_PATH`).
- Nginx:
  - Reverse proxy hacia FastAPI.
  - Sirve `/processed/` directamente desde NFS montado en el host.
- Redis:
  - Broker de tareas y backend de resultados para Celery.
- NFS Server:
  - Exporta `/exports` (fsid=0) que contiene `uploads/`, `processed/`, `assets/`.
- RDS PostgreSQL:
  - Almacena datos de usuarios, videos y estados.

### 6) Flujos principales
1. Upload de video:
   - Cliente → Web Server (FastAPI) → guarda archivo en `uploads/` (NFS) y crea registro en DB.
   - Encola tarea Celery con `video_id` y ruta original.
2. Procesamiento:
   - Worker toma la tarea, lee original desde NFS, procesa y escribe resultado en `processed/` (NFS).
   - Actualiza estado en DB y, opcionalmente, elimina original.
3. Consumo de resultado:
   - Cliente consulta endpoint de videos del usuario → recibe URLs apuntando a `/processed/` servidas por Nginx.

### 7) Operación y despliegue

Scripts:
- `scripts/aws-setup.sh --nfs-role server|client|none`
  - `server`: prepara directorios `/srv/nfs/*` y guía para levantar el contenedor NFS (`docker/compose.file-server.yml`).
  - `client`: instala cliente NFS, monta `./uploads`, `./processed`, `./assets` desde `${NFS_SERVER_IP}` (NFSv4.1) y deja todo listo para `docker compose` (app o worker).
- `scripts/nfs-server-mount.sh`: crea `/srv/nfs/uploads`, `/srv/nfs/processed`, `/srv/nfs/assets` y ajusta permisos.
- `scripts/nfs-client-mount.sh`: instala cliente NFS (si falta), valida puerto 2049, crea remotos si faltan y monta en el repo local.
- `scripts/nfs-client-unmount.sh`: desmonta `./uploads`, `./processed`, `./assets`.

Compose por instancia:
- File Server: `docker/compose.file-server.yml`
- Web App: `docker/compose.app.yml`
- Worker: `docker/compose.worker.yml`

Variables relevantes:
- `STORAGE_BACKEND=local|nfs` → selecciona `LocalStorage` o `NFSStore` (con `fsync`).
- `NFS_SERVER_IP` → IP privada del File Server (para clientes).
- `UPLOAD_PATH`, `PROCESSED_PATH`, `ASSETS_DIR` → rutas internas de contenedor.

### 8) Consideraciones de seguridad
- Limitar `PERMITTED` en el NFS server al rango CIDR de la VPC.
- Usar `SYNC=sync` si se requiere durabilidad estricta (con impacto en rendimiento).
- Permisos de directorios en NFS iniciales amplios (0777) para compatibilidad; ajustar según políticas.
- Credenciales y secretos gestionados por variables de entorno.

### 9) Plan de escalabilidad
- Escalar horizontalmente Web Server y Worker (replicas), manteniendo NFS como punto único para archivos compartidos.
- Redis administrado (o contenedor dedicado) según carga.
- RDS con instancias y almacenamiento ajustables.

### 10) Trabajo futuro
- CDN delante de Nginx para distribuir contenido de `processed/`.
- Observabilidad: métricas y logs centralizados.
- Hardening de NFS y rotación de credenciales.

### 11) Evidencias de cumplimiento
- (50%) Despliegue de Web, Worker y NFS en tres instancias separadas mediante scripts y compose por instancia.
- (10%) Configuración de Amazon RDS como base de datos relacional de la aplicación.

[Espacio para evidencias y capturas]

### 12) Correcciones SonarQube

Esta sección recopila las correcciones realizadas a partir de hallazgos de SonarQube. Por cada corrección se documenta el problema, la acción tomada y la justificación.


- Primera correcion:
  - Problema detectado: Uso de API de autenticación con invocación incorrecta (Severidad: Major).
  - Archivo afectado : `app/api/routes/auth.py`.
  - Corrección aplicada: reemplazo de llamada a `OAuth2PasswordRequestForm` por lectura directa de `request.form()` para extraer `username` y `password`.
  - Justificación: evita invocar un objeto no llamable, simplifica el manejo de `application/x-www-form-urlencoded` y alinea con FastAPI.

- Segunda  corrección: eliminar literal duplicado para imagen de intro/outro
  - Archivo afectado: `app/celery_worker.py`
  - Problema: el literal "intro-outro.jpg" estaba duplicado en tres constantes (`INTRO`, `OUTRO`, `INTRO_OUTRO_IMG`).
  - Solución: se creó la constante `INTRO_OUTRO_FILENAME` y se referenció desde las tres rutas para evitar duplicidad.
  - Justificación: mejora mantenibilidad y cumple la regla de SonarQube sobre duplicación de literales.

- Tercera corrección: reducir complejidad cognitiva y usar API asíncrona de archivos
  - Archivo afectado: `app/core/storage.py`
  - Problema: Complejidad Cognitiva alta (regla `python:S3776`) y uso de `open()` síncrono dentro de funciones `async`.
  - Solución: extracción de helpers `_iterate_chunks` y `_write_stream_to_file` para simplificar el flujo y uso de `aiofiles` en `save_async` de `LocalStorage` y `NFSStore`. Se mantiene `fsync` para durabilidad en NFS.
  - Justificación: mejora mantenibilidad, reduce la complejidad a lo permitido y alinea con buenas prácticas de E/S asíncrona.

- Cuarta corrección: se soluciona con la corrección del punto 3.