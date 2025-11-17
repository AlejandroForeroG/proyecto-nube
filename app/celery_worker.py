import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import shutil

from celery import Celery

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.utils import video_utils as vu
from app.models import Video, VideoStatus
from app.core.storage import is_s3_uri, parse_s3_uri
import boto3

UTC = timezone.utc

try:
    celery_app = Celery("worker", broker="sqs://")
    celery_app.conf.update(
        task_default_queue=settings.SQS_QUEUE_NAME,
        broker_transport_options={
            "region": settings.AWS_REGION or "us-east-1",
            "visibility_timeout": settings.SQS_VISIBILITY_TIMEOUT,
            "wait_time_seconds": settings.SQS_WAIT_TIME_SECONDS,
        },
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )
    celery_app.conf.result_backend = None
    celery_app.conf.task_always_eager = (
        bool(int(os.getenv("CELERY_EAGER", "0"))) or settings.TESTING
    )
    celery_app.conf.task_eager_propagates = True

except Exception as e:
    print(f"Error inicializando Celery/Redis: {e}")
    celery_app = None

ASSETS_DIR = Path(getattr(settings, "ASSETS_DIR", "assets"))
INTRO_OUTRO_FILENAME = "intro-outro.jpg"
INTRO = ASSETS_DIR / INTRO_OUTRO_FILENAME
OUTRO = ASSETS_DIR / INTRO_OUTRO_FILENAME
WATERMARK = ASSETS_DIR / "watermark.png"
INTRO_OUTRO_IMG = ASSETS_DIR / INTRO_OUTRO_FILENAME


def process_video(video_db_id: int, original_path: str):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        local_input = td / "input.mp4"
        trimmed = td / "trimmed.mp4"
        v720 = td / "v720.mp4"
        muted = td / "muted.mp4"
        wm = td / "wm.mp4"
        final_tmp = td / "final.mp4"

        s3_bucket = None
        s3_key = None
        if is_s3_uri(original_path):
            s3_bucket, s3_key = parse_s3_uri(original_path)
            s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
            s3_client.download_file(s3_bucket, s3_key, str(local_input))
        else:
            local_input = Path(original_path)

        vu.trim_to_seconds(str(local_input), str(trimmed), seconds=30)
        vu.scale_to_720p(str(trimmed), str(v720))
        vu.remove_audio(str(v720), str(muted), reencode=False)
        vu.add_watermark(str(muted), str(wm), watermark_path=str(Path(WATERMARK)))
        vu.add_image_intro_outro(str(Path(INTRO_OUTRO_IMG)), str(wm), str(final_tmp))


        if s3_bucket:
            dest_key = f"{settings.S3_PROCESSED_PREFIX}/{video_db_id}_processed.mp4"
            s3_client.upload_file(str(final_tmp), s3_bucket, dest_key)
        
            if s3_key:
                try:
                    s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                except Exception as delete_exc:
                    print(f"Error al eliminar original S3 s3://{s3_bucket}/{s3_key}: {delete_exc}")
            return f"s3://{s3_bucket}/{dest_key}"
        else:
            final_out = os.path.join(
                settings.PROCESSED_PATH, f"{video_db_id}_processed.mp4"
            )
            Path(settings.PROCESSED_PATH).mkdir(parents=True, exist_ok=True)
            shutil.move(str(final_tmp), final_out)
            return final_out


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=1200)
def process_video_task(self, video_db_id: int, original_path: str):
    db = SessionLocal()
    video = None
    try:
        video = db.query(Video).filter(Video.id == video_db_id).first()
        if not video:
            raise ValueError(f"Video with id {video_db_id} not found")

        if video.status in (VideoStatus.processing.value, VideoStatus.done.value):
            return video.processed_path

        updated_rows = (
            db.query(Video)
            .filter(
                Video.id == video_db_id,
                Video.status == VideoStatus.uploaded.value,
            )
            .update({"status": VideoStatus.processing.value, "updated_at": datetime.now(UTC)}, synchronize_session=False)
        )
        db.commit()
        if updated_rows == 0:
            video = db.query(Video).filter(Video.id == video_db_id).first()
            return getattr(video, "processed_path", None)

        v_processed = process_video(video_db_id, original_path)
        video.processed_path = v_processed
        video.updated_at = datetime.now(UTC)
        video.status = VideoStatus.done.value
        db.commit()
        try:
            if original_path and os.path.exists(original_path):
                os.remove(original_path)
        except Exception as delete_exc:
            print(
                f"Error al eliminar el archivo original: {original_path}: {delete_exc}"
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
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()
