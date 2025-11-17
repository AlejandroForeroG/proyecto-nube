#!/usr/bin/env python3
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Iterable, List

from dotenv import load_dotenv

# Cargar variables de entorno de .env si existen
load_dotenv()

from app.core.database import SessionLocal
from app.models.models import Video, VideoStatus

UTC = timezone.utc


def read_task_ids_from_log(log_path: Path) -> List[str]:
    if not log_path.exists():
        raise FileNotFoundError(f"No existe el archivo de tareas: {log_path}")
    ids: List[str] = []
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ids.append(line)
    if not ids:
        raise RuntimeError(f"No se encontraron task_ids en {log_path}")
    return ids


def to_minutes(seconds: float) -> float:
    return seconds / 60.0


def compute_metrics_from_videos(videos: List[Video]) -> dict:
    total = len(videos)
    done = [v for v in videos if v.status == VideoStatus.done.value]
    failed = [v for v in videos if v.status == VideoStatus.failed.value]
    processing = [v for v in videos if v.status == VideoStatus.processing.value]
    uploaded = [v for v in videos if v.status == VideoStatus.uploaded.value]

    if not videos:
        raise RuntimeError("No hay registros de Video para el criterio especificado")

    # Ventana: desde el primer uploaded_at al último updated_at de 'done'
    start_ts = min((v.uploaded_at for v in videos if v.uploaded_at is not None), default=None)
    end_ts = max((v.updated_at for v in done if v.updated_at is not None), default=None)

    throughput_videos_per_min = None
    if start_ts and end_ts and end_ts > start_ts:
        elapsed_minutes = to_minutes((end_ts - start_ts).total_seconds())
        throughput_videos_per_min = len(done) / elapsed_minutes if elapsed_minutes > 0 else None

    # "S" aproximado: (updated_at - uploaded_at) por video done
    service_times_sec = []
    for v in done:
        if v.uploaded_at and v.updated_at and v.updated_at >= v.uploaded_at:
            service_times_sec.append((v.updated_at - v.uploaded_at).total_seconds())

    service_avg_s = mean(service_times_sec) if service_times_sec else None
    service_p50_s = median(service_times_sec) if service_times_sec else None

    return {
        "total": total,
        "done": len(done),
        "failed": len(failed),
        "processing": len(processing),
        "uploaded": len(uploaded),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "throughput_videos_per_min": throughput_videos_per_min,
        "service_avg_seconds": service_avg_s,
        "service_p50_seconds": service_p50_s,
    }


def compute_metrics_for_tasks(task_ids: Iterable[str]) -> dict:
    db = SessionLocal()
    try:
        videos: List[Video] = (
            db.query(Video).filter(Video.task_id.in_(list(task_ids))).all()
        )
    finally:
        db.close()

    return compute_metrics_from_videos(videos)


def compute_metrics_for_file(original_path: str) -> dict:
    db = SessionLocal()
    try:
        videos: List[Video] = (
            db.query(Video).filter(Video.original_path == original_path).all()
        )
    finally:
        db.close()
    return compute_metrics_from_videos(videos)


def write_csv(output_csv: Path, metrics: dict) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    headers = list(metrics.keys())
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(metrics)


def format_ts(ts: datetime | None) -> str:
    return ts.astimezone(UTC).isoformat() if isinstance(ts, datetime) else "-"


def main():
    parser = argparse.ArgumentParser(description="Compute worker throughput and service time (Escenario 2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tasks-log", help="Ruta al archivo .log generado por inject_worker_tasks.py")
    group.add_argument("--file", help="Filtrar métricas por original_path (s3://... o ruta local)")
    parser.add_argument("--output-csv", default=None, help="Ruta opcional para guardar métricas en CSV")
    args = parser.parse_args()

    if args.tasks_log:
        task_log = Path(args.tasks_log)
        task_ids = read_task_ids_from_log(task_log)
        metrics = compute_metrics_for_tasks(task_ids)
        context_str = f"Tasks input:          {task_log}"
    else:
        metrics = compute_metrics_for_file(args.file)
        context_str = f"Filter original_path: {args.file}"

    print("\n=== Métricas Escenario 2 (Worker) ===")
    print(context_str)
    print(f"Total videos:         {metrics['total']}")
    print(f"Done / Failed:        {metrics['done']} / {metrics['failed']}")
    print(f"Processing / Uploaded:{metrics['processing']} / {metrics['uploaded']}")
    print(f"Window start (UTC):   {format_ts(metrics['start_ts'])}")
    print(f"Window end (UTC):     {format_ts(metrics['end_ts'])}")
    if metrics['throughput_videos_per_min'] is not None:
        print(f"Throughput X:         {metrics['throughput_videos_per_min']:.2f} videos/min")
    else:
        print("Throughput X:         -")
    if metrics['service_avg_seconds'] is not None:
        print(f"S promedio:           {metrics['service_avg_seconds']:.2f} s")
    else:
        print("S promedio:           -")
    if metrics['service_p50_seconds'] is not None:
        print(f"S p50:                {metrics['service_p50_seconds']:.2f} s")
    else:
        print("S p50:                -")
    print("=====================================\n")

    if args.output_csv:
        out_csv = Path(args.output_csv)
        write_csv(out_csv, metrics)
        print(f"CSV guardado en: {out_csv}")


if __name__ == "__main__":
    main()


