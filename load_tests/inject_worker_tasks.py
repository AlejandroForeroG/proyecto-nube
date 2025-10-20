#!/usr/bin/env python3

import argparse
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_PATH = os.getenv("UPLOAD_PATH", "./load_tests/test_files")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app_user:app_password@localhost:5432/app_db"
)

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

def inject_tasks(
    count: int,
    size_mb: int,
    mode: str = "burst",
    rate: int = 10,
    redis_url: str = REDIS_URL,
) -> List[str]:
    celery_app = Celery("worker", broker=redis_url, backend=redis_url)
    test_file_path = Path(UPLOAD_PATH) / f"test_video_{size_mb}MB.mp4"
    if not test_file_path.exists():
        create_test_video_file(size_mb, test_file_path)
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
    for i in range(count):
        video_db_id = i + 10000
        from app.celery_worker import process_video_task
        task = process_video_task.apply_async(
            args=[video_db_id, str(test_file_path)], task_id=f"load-test-{uuid.uuid4()}"
        )
        task_ids.append(task.id)
        print(f"[{i + 1}/{count}] Enqueued task {task.id} (video_id={video_db_id})")
        if mode == "sustained" and i < count - 1:
            delay = 60.0 / rate
            time.sleep(delay)
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
    )
    if args.monitor:
        monitor_tasks(task_ids, args.redis_url)
    else:
        print("\nTip: Use --monitor flag to track task progress")

if __name__ == "__main__":
    main()
