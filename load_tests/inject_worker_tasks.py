#!/usr/bin/env python3

import argparse
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from celery import Celery
from dotenv import load_dotenv

from app.core.database import SessionLocal
from app.models import User, Video, VideoStatus

# Cargar variables de entorno desde .env lo antes posible
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_PATH = os.getenv("UPLOAD_PATH", "./load_tests/test_files")


def create_test_video_file(size_mb: int, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    size_bytes = size_mb * 1024 * 1024
    chunk_size = 1024 * 1024
    print(f"Creating test file: {output_path} ({size_mb}MB)")
    with open(output_path, "wb") as f:
        written = 0
        while written < size_bytes:
            chunk = os.urandom(min(chunk_size, size_bytes - written))
            f.write(chunk)
            written += len(chunk)
    return output_path


def resolve_test_file(size_mb: int, file_arg: Optional[str], no_generate: bool) -> Path:
    if file_arg:
        p = Path(file_arg)
        if not p.exists():
            raise FileNotFoundError(f"Provided --file does not exist: {p}")
        return p
    # Por defecto generar bajo UPLOAD_PATH para que el Worker lo vea (NFS)
    test_file_path = Path(UPLOAD_PATH) / "test_files" / f"test_video_{size_mb}MB.mp4"
    if test_file_path.exists():
        return test_file_path
    if no_generate:
        raise FileNotFoundError(
            f"Test file not found and --no-generate set: {test_file_path}"
        )
    return create_test_video_file(size_mb, test_file_path)


def get_default_user_id(db) -> int:
    u = db.query(User).first()
    if not u:
        raise RuntimeError(
            "No users found in DB. Create a user or provide --user-id explicitly."
        )
    return int(u.id)


def create_video_record(db, user_id: int, original_path: str, title: str) -> Video:
    v = Video(
        video_id=str(uuid.uuid4()),
        title=title,
        status=VideoStatus.uploaded.value,
        original_path=original_path,
        user_id=user_id,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def inject_tasks(
    count: int,
    size_mb: int,
    mode: str = "burst",
    rate: int = 10,
    redis_url: str = REDIS_URL,
    file_arg: Optional[str] = None,
    no_generate: bool = False,
    user_id: Optional[int] = None,
) -> List[str]:
    # Validar conectividad con Redis creando una app Celery (evita errores de env)
    _ = Celery("worker", broker=redis_url, backend=redis_url)
    test_file_path = resolve_test_file(size_mb, file_arg, no_generate)
    task_ids = []
    print(f"\n{'=' * 60}")
    print("INJECTING TASKS - Scenario 2 (Worker Throughput)")
    print(f"{'=' * 60}")
    print(f"Mode: {mode}")
    print(f"Count: {count}")
    print(f"Video Size: {size_mb}MB")
    print(f"File: {test_file_path}")
    if mode == "sustained":
        print(f"Rate: {rate} tasks/minute")
    print(f"{'=' * 60}\n")
    start_time = time.time()
    db = SessionLocal()
    for i in range(count):
        try:
            resolved_user_id = int(user_id) if user_id else get_default_user_id(db)
            title = f"Load Test Video {size_mb}MB #{i + 1}"
            v = create_video_record(db, resolved_user_id, str(test_file_path), title)
            from app.celery_worker import process_video_task

            task = process_video_task.apply_async(
                args=[v.id, str(test_file_path)], task_id=f"load-test-{uuid.uuid4()}"
            )
            v.task_id = task.id
            db.commit()
            task_ids.append(task.id)
            print(f"[{i + 1}/{count}] Enqueued task {task.id} (db_video_id={v.id})")
        except Exception as exc:
            print(f"Error enqueuing task #{i + 1}: {exc}")
            continue
        if mode == "sustained" and i < count - 1:
            delay = 60.0 / rate
            time.sleep(delay)
    db.close()
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print("INJECTION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total tasks: {count}")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Injection rate: {count / elapsed * 60:.2f} tasks/min")
    print(f"Task IDs: {len(task_ids)}")
    print(f"{'=' * 60}\n")
    log_file = Path(
        f"./load_tests/results/worker_tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w") as f:
        f.write(f"# Worker Load Test - {datetime.now()}\n")
        f.write(f"# Mode: {mode}, Count: {count}, Size: {size_mb}MB\n")
        f.write(f"# Injection rate: {count / elapsed * 60:.2f} tasks/min\n\n")
        for task_id in task_ids:
            f.write(f"{task_id}\n")
    print(f"Task IDs saved to: {log_file}")
    return task_ids


def monitor_tasks(task_ids: List[str], redis_url: str = REDIS_URL):
    celery_app = Celery("worker", broker=redis_url, backend=redis_url)
    print(f"\n{'=' * 60}")
    print("MONITORING TASKS")
    print(f"{'=' * 60}")
    print(f"Total tasks: {len(task_ids)}")
    print("Press Ctrl+C to stop monitoring\n")
    try:
        while True:
            pending = 0
            processing = 0
            success = 0
            failed = 0
            for task_id in task_ids:
                result = celery_app.AsyncResult(task_id)
                state = result.state
                if state == "PENDING":
                    pending += 1
                elif state == "STARTED":
                    processing += 1
                elif state == "SUCCESS":
                    success += 1
                elif state == "FAILURE":
                    failed += 1
            print(
                f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                f"Pending: {pending:3d} | "
                f"Processing: {processing:3d} | "
                f"Success: {success:3d} | "
                f"Failed: {failed:3d}",
                end="",
                flush=True,
            )
            if pending == 0 and processing == 0:
                print("\n\nAll tasks completed!")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")


def main():
    parser = argparse.ArgumentParser(
        description="Inject video processing tasks for worker throughput testing"
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of tasks to inject (default: 10)"
    )
    parser.add_argument(
        "--size",
        type=str,
        default="50MB",
        choices=["50MB", "100MB", "200MB"],
        help="Video file size (default: 50MB)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="burst",
        choices=["burst", "sustained", "saturation"],
        help="Injection mode: burst (all at once), sustained (controlled rate), saturation (max load)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=10,
        help="Tasks per minute for sustained mode (default: 10)",
    )
    parser.add_argument(
        "--redis-url",
        type=str,
        default=REDIS_URL,
        help=f"Redis URL (default: {REDIS_URL})",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Use existing video file path (must be accessible to Worker)",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Do not generate a test file if it does not exist",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="User ID owner of created Video rows (defaults to first user)",
    )
    parser.add_argument(
        "--monitor", action="store_true", help="Monitor task progress after injection"
    )
    args = parser.parse_args()
    size_mb = int(args.size.replace("MB", ""))
    task_ids = inject_tasks(
        count=args.count,
        size_mb=size_mb,
        mode=args.mode,
        rate=args.rate,
        redis_url=args.redis_url,
        file_arg=args.file,
        no_generate=args.no_generate,
        user_id=args.user_id,
    )
    if args.monitor:
        monitor_tasks(task_ids, args.redis_url)
    else:
        print("\nTip: Use --monitor flag to track task progress")


if __name__ == "__main__":
    main()
