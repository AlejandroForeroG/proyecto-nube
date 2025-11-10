import asyncio
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, BinaryIO, Iterable
from urllib.parse import urlparse

import aiofiles
import boto3

from app.core.config import settings


class StoragePort(ABC):
    @abstractmethod
    def save(self, file: BinaryIO, dest_path: str) -> None: ...


class LocalStorage(StoragePort):
    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_PATH)

    def save(self, file: BinaryIO | Iterable[bytes], dest_path: str) -> str:
        full_path = self.base_dir / dest_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as out:
            if hasattr(file, "read"):
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    out.write(chunk)
            else:
                for chunk in file:
                    out.write(chunk)
        return str(full_path)

    async def save_async(
        self,
        file: Any | AsyncIterable[bytes],
        dest_path: str,
        *,
        chunk_size: int = 1024 * 1024,
        max_size: int | None = None,
    ) -> str:
        full_path = self.base_dir / dest_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(full_path, "wb") as out:
            await _write_stream_to_file(
                file, out, chunk_size=chunk_size, max_size=max_size
            )

        return str(full_path)


class NFSStore(LocalStorage):
    """
    Storage backend optimizado para NFS.
    """

    def save(self, file: BinaryIO | Iterable[bytes], dest_path: str) -> str:
        full_path = self.base_dir / dest_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Guardando archivo en: {full_path}")
        try:
            with open(full_path, "wb") as out:
                out.flush()
                if hasattr(file, "read"):
                    for chunk in iter(lambda: file.read(1024 * 1024), b""):
                        out.write(chunk)
                else:
                    for chunk in file:
                        out.write(chunk)

                os.fsync(out.fileno())

        except Exception:
            raise
        return str(full_path)

    async def save_async(
        self,
        file: Any | AsyncIterable[bytes],
        dest_path: str,
        *,
        chunk_size: int = 1024 * 1024,
        max_size: int | None = None,
    ) -> str:
        full_path = self.base_dir / dest_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(full_path, "wb") as out:
                await _write_stream_to_file(
                    file, out, chunk_size=chunk_size, max_size=max_size
                )
                await out.flush()

            fd = os.open(full_path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

            return str(full_path)
        except Exception as e:
            print(f"Error al guardar el archivo (async): {e}")
            raise


def is_s3_uri(uri: str | None) -> bool:
    if not uri:
        return False
    return str(uri).startswith("s3://")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """
    Retorna (bucket, key) a partir de un URI s3://bucket/key
    """
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")


def _get_s3_client():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def generate_presigned_get_url(s3_uri: str, expires: int | None = None) -> str:
    """
    Genera una URL prefirmada GET para un URI S3.
    """
    bucket, key = parse_s3_uri(s3_uri)
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires or settings.S3_URL_EXPIRE_SECONDS,
    )


class S3Storage(StoragePort):
    def __init__(
        self,
        bucket: str | None = None,
        upload_prefix: str | None = None,
    ):
        self.bucket = bucket or (settings.AWS_S3_BUCKET or "")
        self.upload_prefix = (upload_prefix or settings.S3_UPLOAD_PREFIX).rstrip("/")
        if not self.bucket:
            raise ValueError("AWS_S3_BUCKET no configurado")

    def _build_key(self, dest_path: str) -> str:
        dest = dest_path.lstrip("/")
        if self.upload_prefix:
            return f"{self.upload_prefix}/{dest}"
        return dest

    def save(self, file: BinaryIO | Iterable[bytes], dest_path: str) -> str:
        client = _get_s3_client()
        key = self._build_key(dest_path)

        try:
            if hasattr(file, "read"):
                client.upload_fileobj(file, self.bucket, key)  # type: ignore[arg-type]
            else:
                with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
                    tmp_path = tmp.name
                    for chunk in file:
                        tmp.write(chunk)
                try:
                    client.upload_file(tmp_path, self.bucket, key)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        except Exception:
            raise
        return f"s3://{self.bucket}/{key}"

    async def save_async(
        self,
        file: Any | AsyncIterable[bytes],
        dest_path: str,
        *,
        chunk_size: int = 1024 * 1024,
        max_size: int | None = None,
    ) -> str:
        key = self._build_key(dest_path)
        client = _get_s3_client()

        tmp_fd, tmp_path = tempfile.mkstemp()
        os.close(tmp_fd)
        try:
            async with aiofiles.open(tmp_path, "wb") as out:
                await _write_stream_to_file(
                    file, out, chunk_size=chunk_size, max_size=max_size
                )

            await asyncio.to_thread(client.upload_file, tmp_path, self.bucket, key)
        except Exception as e:
            print(f"Error al subir a S3: {e}")
            raise
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return f"s3://{self.bucket}/{key}"


async def _iterate_chunks(
    source: Any | AsyncIterable[bytes],
    *,
    chunk_size: int,
) -> AsyncGenerator[bytes, None]:
    read_method = getattr(source, "read", None)
    if read_method and getattr(read_method, "__call__", None):
        while True:
            chunk = await source.read(chunk_size)
            if not chunk:
                break
            yield chunk
    else:
        async for chunk in source:  # type: ignore
            yield chunk


async def _write_stream_to_file(
    source: Any | AsyncIterable[bytes],
    out_file,
    *,
    chunk_size: int,
    max_size: int | None,
) -> None:
    total = 0
    async for chunk in _iterate_chunks(source, chunk_size=chunk_size):
        total += len(chunk)
        if max_size is not None and total > max_size:
            raise ValueError("file too large")
        await out_file.write(chunk)


def get_storage(
    base_dir: str | Path | None = None, storage_backend: str = "nfs"
) -> StoragePort:
    base = base_dir or getattr(settings, "UPLOAD_PATH", "uploads")

    if storage_backend == "s3":
        return S3Storage()

    if storage_backend == "nfs":
        return NFSStore(base_dir=base)

    return LocalStorage(base_dir=base)
