
# Entrega Semana 1

Esta entrega compila los artefactos iniciales de arquitectura, diseño y operación del proyecto.
# Test implementados
## Test unitarioss
### Autenticación

- **HU: Signup** — `POST /api/auth/signup`  
  Tests:  
    - `tests/test_auth.py::test_signup_and_login_json` (201)  
    - `tests/test_auth.py::test_signup_duplicate_email` (400)  
  Huecos:  
    - 422 (validación de payload)

- **HU: Login** — `POST /api/auth/login`  
  Tests:  
    - `tests/test_auth.py::test_signup_and_login_json` (200)  
    - `tests/test_auth.py::test_login_invalid_credentials` (401)  
  Huecos:  
    - n/a explícitos en el OpenAPI

---

### Videos (privados)

- **HU: Subir video** — `POST /api/videos/upload`  
  Tests:  
    - `tests/test_videos.py::test_upload_video_creates_record` (201)  
    - `tests/test_videos.py::test_upload_video_invalid_type` (400 tipo inválido)  
  Huecos:  
    - 401 (no autenticado), 400 (archivo demasiado grande)

- **HU: Listar videos del usuario** — `GET /api/videos/user`  
  Tests:  
    - `tests/test_videos.py::test_get_user_videos_lists_processed` (200, filtra a procesados del usuario)  
  Huecos:  
    - 401 (no autenticado)

- **HU: Listar videos (general)** — `GET /api/videos`  
  Tests:  
    - *sin cobertura actual*  
  Huecos:  
    - 200, 401

- **HU: Detalle de video** — `GET /api/videos/{video_id}`  
  Tests:  
    - `tests/test_videos.py::test_video_detail_includes_urls_and_votes` (200)  
  Huecos:  
    - 401 (no autenticado), 422 (path param inválido)

- **HU: Eliminar video** — `DELETE /api/videos/{video_id}`  
  Tests:  
    - `tests/test_videos.py::test_delete_video_success` (200)
    - `tests/test_videos.py::test_delete_video_forbidden_other_user` (403)
    - `tests/test_videos.py::test_delete_video_bad_request_if_public` (400)
  Huecos:  
    - 401 (no autenticado), 404 (no existe o no pertenece)

---

### Público

- **HU: Listado público** — `GET /api/public/videos`  
  Tests:  
    - `tests/test_public.py::test_list_public_videos_only_processed` (200)  
  Huecos:  
    - n/a relevantes

- **HU: Votar video público** — `POST /api/public/videos/{video_id}/vote`  
  Tests:  
    - `tests/test_public.py::test_vote_public_video_once_only` (200 y 400 por voto repetido)
    - `tests/test_public.py::test_vote_public_video_requires_auth` (401)
  Huecos:  
    - 404 (video no encontrado)

- **HU: Rankings** — `GET /api/public/rankings`  
  Tests:  
    - `tests/test_public.py::test_rankings_with_and_without_city` (200 con y sin city, orden por votos)  
  Huecos:  
    - 400 (parámetro inválido)

---

### Salud

- **HU: Healthcheck** — `GET /health`  
  Tests:  
    - `tests/test_health.py::test_health` (200, body `{"status":"ok"}`)

# Arquitectura
## 1. Modelo de datos (ERD)

- Descripción: Estructura de entidades principales (User, Video, Vote) y sus relaciones.
- Diagrama ERD: [Ver imagen](../../imagenes/semana_1/erd.png)

## 2. Documentación de la API (Postman)

- Endpoints principales (autenticación, carga de videos, listado de videos del usuario, estado de salud).
- Colección de Postman: [Descargar](../../postman/semana_1_collection.json)
- Evidencia de ejecución (capturas): [Ver carpeta](../../imagenes/semana_1/postman/)

## 3. Diagrama de componentes

- Componentes: Backend (FastAPI), Worker (Celery), Broker (Redis), Base de datos (Postgres), Reverse proxy (Nginx).
- Diagrama: [Ver imagen](../../imagenes/semana_1/componentes.png)

## 4. Diagrama de flujo de procesos

- Etapas: Carga -> Almacenamiento -> Encolamiento -> Procesamiento (ffmpeg) -> Publicación -> Consulta.
- Diagrama: [Ver imagen](../../imagenes/semana_1/flujo_procesos.png)

## 5. Despliegue e infraestructura

- Infraestructura: Contenedores Docker orquestados con Docker Compose.
- Descripción de servicios activos: Nginx, API, Celery Worker, Redis, Postgres.
- Diagrama de despliegue: [Ver imagen](../../imagenes/semana_1/despliegue.png)
- Guía reproducible: ver README (sección "Cómo inicializar") y script de despliegue.

## 6. Reporte de análisis de SonarQube

- Resultado del último análisis sobre `main`:
  - Bugs: <indicar>
  - Vulnerabilidades: <indicar>
  - Code Smells: <indicar>
  - Cobertura de pruebas: <indicar>%
  - Duplicación de código: <indicar>%
  - Quality Gate: Aprobado/Rechazado
- Evidencia: [Captura del dashboard](../../imagenes/semana_1/sonarqube.png)

---

TODO:
- Completar los enlaces a imágenes y artefactos en `docs/imagenes/semana_1/` y `docs/postman/`.
- Mantener este documento actualizado conforme avancen los artefactos.


