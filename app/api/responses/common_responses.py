from http import HTTPStatus

from app.api.schemas.schemas import ErrorMessage

unauthorized_response = {
    HTTPStatus.UNAUTHORIZED: {
        "model": ErrorMessage,
        "description": "Credenciales invalidas",
        "content": {
            "application/json": {"example": {"detail": "Credenciales invalidas"}}
        },
        "status_code": HTTPStatus.UNAUTHORIZED,
    },
}
