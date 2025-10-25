import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.utils import video_utils as vu
from app.models import Video, VideoStatus


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
    celery_app.conf.task_eager_propagates = True

except Exception as e:
    print(f"Error inicializando Celery/Redis: {e}")
    celery_app = None 

ASSETS_DIR = Path(getattr(settings, "ASSETS_DIR", "assets"))
INTRO = ASSETS_DIR / "intro-outro.jpg"
OUTRO = ASSETS_DIR / "intro-outro.jpg"
WATERMARK = ASSETS_DIR / "watermark.png"
INTRO_OUTRO_IMG = ASSETS_DIR / "intro-outro.jpg"


def process_video(video_db_id: int, original_path: str):
    final_out = os.path.join(settings.PROCESSED_PATH, f"{video_db_id}_processed.mp4")
    Path(settings.PROCESSED_PATH).mkdir(parents=True, exist_ok=True)
    return "Path to the processed video"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        trimmed = td / "trimmed.mp4"
        v720 = td / "v720.mp4"
        muted = td / "muted.mp4"
        wm = td / "wm.mp4"

    
        vu.trim_to_seconds(original_path, str(trimmed), seconds=30)
        vu.scale_to_720p(str(trimmed), str(v720))
        vu.remove_audio(str(v720), str(muted), reencode=False)
        vu.add_watermark(str(muted), str(wm), watermark_path=str(Path(WATERMARK)))
        vu.add_image_intro_outro(str(Path(INTRO_OUTRO_IMG)), str(wm), final_out)
        return final_out


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=1200)
def process_video_task(self, video_db_id: int, original_path: str):
    db = SessionLocal()
    video = None
    try:
        video = db.query(Video).filter(Video.id == video_db_id).first()
        if not video:
            raise ValueError(f"Video with id {video_db_id} not found")
        video.status = VideoStatus.processing.value
        db.commit()
        v_processed = process_video(video_db_id, original_path)
        video.processed_path = v_processed
        video.updated_at = datetime.now(UTC)
        video.status = VideoStatus.done.value
        db.commit()
        try:
            if original_path and os.path.exists(original_path):
                os.remove(original_path)
        except Exception as delete_exc:
            print(f"Error al eliminar el archivo original: {original_path}: {delete_exc}")
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
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()
