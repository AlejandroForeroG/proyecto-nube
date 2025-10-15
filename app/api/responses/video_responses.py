from http import HTTPStatus
from typing import List

from app.api.responses.common_responses import unauthorized_response
from app.api.schemas.schemas import ErrorMessage
from app.api.schemas.videos import (
    DeleteVideoResponse,
    UploadVideoResponse,
    UserVideoResponse,
    VideoDetailResponse,
)

upload_video_responses = {
    **unauthorized_response,
    HTTPStatus.CREATED: {
        "model": UploadVideoResponse,
        "description": "Video subido correctamente. Procesamiento en progeso.",
        "status_code": HTTPStatus.CREATED,
        "content": {
            "application/json": {
                "example": {
                    "message": "Video subido correctamente. Procesamiento en progeso.",
                    "task_id": "1234567890",
                }
            }
        },
    },
    HTTPStatus.BAD_REQUEST: {
        "model": ErrorMessage,
        "description": "Solicitud inválida",
        "status_code": HTTPStatus.BAD_REQUEST,
        "content": {
            "application/json": {
                "examples": {
                    "invalid_type": {
                        "summary": "Tipo de archivo inválido",
                        "value": {
                            "detail": "Tipo de archivo invalido, debe ser un video",
                            "status_code": 400,
                        },
                    },
                    "file_too_large": {
                        "summary": "Archivo demasiado grande",
                        "value": {
                            "detail": "El archivo excede el tamaño limite, el tamaño maximo es 100MB",
                            "status_code": 400,
                        },
                    },
                }
            }
        },
    },
}

user_videos_responses = {
    **unauthorized_response,
    HTTPStatus.OK: {
        "model": List[UserVideoResponse],
        "description": "Videos obtenidos correctamente",
        "status_code": HTTPStatus.OK,
        "content": {
            "application/json": {
                "example": {
                    "videos": [
                        {
                            "video_id": "1234567890",
                            "title": "Video 1",
                            "status": "uploaded",
                            "uploaded_at": "2021-01-01",
                            "updated_at": "2021-01-01",
                            "processed_url": "https://example.com/video1.mp4",
                        },
                        {
                            "video_id": "1234567891",
                            "title": "Video 2",
                            "status": "uploaded",
                            "uploaded_at": "2021-01-01",
                            "updated_at": "2021-01-01",
                            "processed_url": "https://example.com/video2.mp4",
                        },
                    ]
                }
            }
        },
    },
}


video_detail_responses = {
    **unauthorized_response,
    HTTPStatus.OK: {
        "model": VideoDetailResponse,
        "description": "Detalle del video obtenido correctamente",
        "status_code": HTTPStatus.OK,
        "content": {
            "application/json": {
                "example": {
                    "video_id": "a1b2c3d4",
                    "title": "Tiros de tres en movimiento",
                    "status": "processed",
                    "uploaded_at": "2025-03-15T14:22:00Z",
                    "processed_at": "2025-03-15T15:10:00Z",
                    "original_url": "https://anb.com/uploads/a1b2c3d4.mp4",
                    "processed_url": "https://anb.com/processed/a1b2c3d4.mp4",
                    "votes": 125,
                }
            }
        },
    },
}


delete_video_responses = {
    **unauthorized_response,
    HTTPStatus.OK: {
        "model": DeleteVideoResponse,
        "description": "El video ha sido eliminado exitosamente.",
        "status_code": HTTPStatus.OK,
        "content": {
            "application/json": {
                "example": {
                    "message": "El video ha sido eliminado exitosamente.",
                    "video_id": "a1b2c3d4",
                }
            }
        },
    },
    HTTPStatus.BAD_REQUEST: {
        "model": ErrorMessage,
        "description": "El video no puede ser eliminado porque no cumple las condiciones",
        "status_code": HTTPStatus.BAD_REQUEST,
        "content": {
            "application/json": {
                "example": {
                    "detail": "El video ya está habilitado para votación o fue publicado",
                }
            }
        },
    },
    HTTPStatus.FORBIDDEN: {
        "model": ErrorMessage,
        "description": "No tiene permisos para eliminar este video",
        "status_code": HTTPStatus.FORBIDDEN,
        "content": {"application/json": {"example": {"detail": "Forbidden"}}},
    },
    HTTPStatus.NOT_FOUND: {
        "model": ErrorMessage,
        "description": "El video no existe o no pertenece al usuario",
        "status_code": HTTPStatus.NOT_FOUND,
        "content": {
            "application/json": {
                "example": {
                    "detail": "Video no encontrado",
                }
            }
        },
    },
}
