import logging
import os

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app.api.routes import auth, public, videos

if os.getenv("ENABLE_CW_LOGS", "true").lower() == "true":
    from app.cloudwatch.LogsHandler import configure_logging
    configure_logging()

app = FastAPI(title="API", description="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])


Instrumentator().add(
    metrics.latency(
        buckets=(
            0.005,
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
            15.0,
            20.0,
        )
    )
).add(metrics.requests()).instrument(app).expose(app)


@app.get("/api/health")
def health():
    return {"status": "ok"}


logger = logging.getLogger("uvicorn.error")


@app.exception_handler(Exception)
async def _error_logger(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse
    import traceback

    try:
        body = await request.json()
    except Exception:
        try:
            raw = await request.body()
            body = raw.decode("utf-8", errors="ignore")
        except Exception:
            body = "<unavailable>"

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        for idx, error in enumerate(errors):
            logger.warning(
                "422 ValidationError #%d on %s %s | error=%s | body=%s",
                idx + 1,
                request.method,
                request.url,
                error,
                body,
            )
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)
    else:
        tb_str = "".join(traceback.format_exception(
            type(exc), exc, exc.__traceback__))
        logger.error(
            "Exception on %s %s | type=%s | detail=%s | body=%s\nTraceback:\n%s",
            request.method,
            request.url,
            type(exc).__name__,
            str(exc),
            body,
            tb_str,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "detail": str(exc),
                "traceback": tb_str
            },
        )
