import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.utils import video_utils as vu
from app.models import Video, VideoStatus


if os.getenv("ENABLE_CW_LOGS", "true").lower() == "true":
    from app.cloudwatch.LogsHandler import configure_logging

    configure_logging()

logger = logging.getLogger(__name__)

UTC = timezone.utc

try:
    celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )

    celery_app.conf.task_always_eager = (
        bool(int(os.getenv("CELERY_EAGER", "0"))) or settings.TESTING
    )
    if celery_app.conf.task_always_eager:
        logger.warning("Celery running in eager mode", extra={"testing": settings.TESTING})
    celery_app.conf.task_eager_propagates = True

except Exception as e:
    logger.exception("Error inicializando Celery/Redis")
    celery_app = None

ASSETS_DIR = Path(getattr(settings, "ASSETS_DIR", "assets"))
INTRO_OUTRO_FILENAME = "intro-outro.jpg"
INTRO = ASSETS_DIR / INTRO_OUTRO_FILENAME
OUTRO = ASSETS_DIR / INTRO_OUTRO_FILENAME
WATERMARK = ASSETS_DIR / "watermark.png"
INTRO_OUTRO_IMG = ASSETS_DIR / INTRO_OUTRO_FILENAME


def process_video(video_db_id: int, original_path: str):
    logger.debug(
        "Starting video processing pipeline",
        extra={"video_db_id": video_db_id, "original_path": original_path},
    )
    final_out = os.path.join(settings.PROCESSED_PATH, f"{video_db_id}_processed.mp4")
    Path(settings.PROCESSED_PATH).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        trimmed = td / "trimmed.mp4"
        v720 = td / "v720.mp4"
        muted = td / "muted.mp4"
        wm = td / "wm.mp4"

        logger.debug("Trimming video", extra={"video_db_id": video_db_id})
        vu.trim_to_seconds(original_path, str(trimmed), seconds=30)
        logger.debug("Scaling video to 720p", extra={"video_db_id": video_db_id})
        vu.scale_to_720p(str(trimmed), str(v720))
        logger.debug("Removing audio", extra={"video_db_id": video_db_id})
        vu.remove_audio(str(v720), str(muted), reencode=False)
        logger.debug("Adding watermark", extra={"video_db_id": video_db_id})
        vu.add_watermark(str(muted), str(wm), watermark_path=str(Path(WATERMARK)))
        logger.debug("Adding intro/outro", extra={"video_db_id": video_db_id})
        vu.add_image_intro_outro(str(Path(INTRO_OUTRO_IMG)), str(wm), final_out)
        logger.info(
            "Video processing pipeline completed",
            extra={"video_db_id": video_db_id, "output_path": final_out},
        )
        return final_out


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=1200)
def process_video_task(self, video_db_id: int, original_path: str):
    db = SessionLocal()
    video = None
    task_id = getattr(getattr(self, "request", None), "id", None)
    logger.info(
        "Process video task started",
        extra={
            "task_id": task_id,
            "video_db_id": video_db_id,
            "original_path": original_path,
        },
    )
    try:
        video = db.query(Video).filter(Video.id == video_db_id).first()
        if not video:
            logger.error(
                "Video not found for processing",
                extra={"video_db_id": video_db_id},
            )
            raise ValueError(f"Video with id {video_db_id} not found")
        video.status = VideoStatus.processing.value
        db.commit()
        logger.debug(
            "Video status updated to processing",
            extra={"video_db_id": video_db_id, "task_id": task_id},
        )
        v_processed = process_video(video_db_id, original_path)
        video.processed_path = v_processed
        video.updated_at = datetime.now(UTC)
        video.status = VideoStatus.done.value
        db.commit()
        logger.info(
            "Video processing completed successfully",
            extra={
                "task_id": task_id,
                "video_db_id": video_db_id,
                "processed_path": v_processed,
            },
        )
        try:
            if original_path and os.path.exists(original_path):
                os.remove(original_path)
                logger.debug(
                    "Original file removed after processing",
                    extra={"video_db_id": video_db_id, "original_path": original_path},
                )
        except Exception as delete_exc:
            logger.warning(
                "Error al eliminar el archivo original",
                extra={"video_db_id": video_db_id, "original_path": original_path},
                exc_info=delete_exc,
            )
        return v_processed
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        if video is not None:
            try:
                video.status = VideoStatus.failed.value
                db.commit()
            except Exception:
                db.rollback()
        logger.exception(
            "Video processing failed; task will retry",
            extra={"task_id": task_id, "video_db_id": video_db_id},
        )
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()
        logger.debug(
            "Database session closed for processing task",
            extra={"task_id": task_id, "video_db_id": video_db_id},
        )
