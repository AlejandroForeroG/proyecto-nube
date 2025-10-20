
# Entrega1

Esta entrega compila los requerimientos solicitados 


## Entregas
- Video sustentación: [Ver video](https://drive.google.com/file/d/1O0dMHBgJviul23iVsieJB4MkeW3ddumX/view?usp=sharing)

- La especificación OpenAPI de la API está disponible un avez inicialice el proyecto en `/docs` del servicio Nginx (por defecto http://localhost:8080/docs).



## Arquitectura
### 1. Modelo de datos
- Diagrama: [Ver imagen](https://drive.google.com/file/d/1E3vjyf7dd5FIm3wkKZc592LTR_fbfzVh/view?usp=sharing)



### 2. Diagrama de componentes

- Diagrama: [Ver imagen](https://drive.google.com/file/d/1oWUE6Pb6KDLkE9c3dGdcvcxo_4quyLJJ/view?usp=sharing)

### 3. Diagrama de flujo de procesos

- Diagrama: [Ver imagen](https://drive.google.com/file/d/1II6ekzOkFpi0cM94-Xo0sNU860MXSn5T/view?usp=sharing)

### 4. Despliegue e infraestructura
- Diagrama de despliegue: [Ver imagen](https://drive.google.com/file/d/1qvCAnbd3ss0VMz3zkSlJ5kmZ7Plf7CAA/view?usp=sharing)
- Guía reproducible: ver README (sección "Cómo inicializar") y script de despliegue.

### 4. Reporte de análisis de SonarQube

- Resultado del último análisis sobre `main`:
- Evidencia: [Captura del dashboard](https://drive.google.com/file/d/1CWt2H1FEXjfCXTFyLwGiEQnKqqg_hLE4/view?usp=sharing)

---

## Test implementados
### Documentación de la API (Postman)

- Endpoints principales (autenticación, carga de videos, listado de videos del usuario, estado de salud).
- Colecciones de Postman (JSON, por dominio) en `collections/`:
  - `collections/auth.postman_collection.json`
  - `collections/public.postman_collection.json`
  - `collections/videos.postman_collection.json`
- Entorno: `collections/postman_environment.json` con variables: `base_url`, `deploy_url`, `root_url`, `token`, `email`, `password`, `upload_file_path`, `invalid_file_path`.
- Ejecución automatizada (Newman dentro de `rest_api`):
  - Previo: `docker compose up -d --build`
  - Ejecutar todas las colecciones (PowerShell):
    ```powershell
    ForEach ($c in @('auth','public','videos')) { docker compose exec rest_api newman run /my-app/collections/$c.postman_collection.json -e /my-app/collections/postman_environment.json --reporters cli }
    ```
  - Ejecutar una colección:
    ```powershell
    docker compose exec rest_api newman run /my-app/collections/public.postman_collection.json -e /my-app/collections/postman_environment.json --reporters cli
    ```
### Test unitarios
#### Autenticación

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

#### Videos (privados)

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

#### Público

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

## Salud

- **HU: Healthcheck** — `GET /health`  
  Tests:  
    - `tests/test_health.py::test_health` (200, body `{"status":"ok"}`)


## Pruebas
- **Plan de pruebas:** Consulte el archivo [`plan_pruebas.md`](plan_pruebas.md), el cual describe detalladamente los escenarios de prueba, los criterios de aceptación (SLOs), el entorno de ejecución y los datos de prueba recomendados.
- **Análisis de capacidad:** Todos los resultados y el análisis correspondiente a cada ejecución deben ser consignados en [`analisis_capacidad.md`](analisis_capacidad.md), siguiendo el formato establecido para facilitar la comparación y validación respecto a los SLOs definidos.

> **Nota:** En el archivo `README.md`  se encuentran instrucciones precisas para la ejecución de las pruebas de carga, tanto mediante Locust (para la capa web) como a través del script `inject_worker_tasks.py` (para la evaluación del worker). Dichas instrucciones contemplan los comandos necesarios, parámetros sugeridos y consideraciones de monitoreo.

## CI/D

Se agregó un pipeline de integración y despliegue continuo (CI/CD) usando **GitHub Actions** en la carpeta `.github/workflows`:

- **Archivo:** `.github/workflows/ci-cd.yml`
- **Qué hace?**
  - Ejecuta automáticamente los tests unitarios en cada push a la rama `dev`.
  - Corre los tests cuando se abre o sincroniza un pull request hacia la rama `staging`.
  - Instala dependencias, realiza checkout del código y muestra el resumen de resultados.



