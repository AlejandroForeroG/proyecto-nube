
# Entrega Semana 1

Esta entrega compila los artefactos iniciales de arquitectura, diseño y operación del proyecto.

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


