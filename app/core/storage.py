from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, AsyncIterable, BinaryIO, Iterable
import os

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
        total = 0
        with open(full_path, "wb") as out:
            read_method = getattr(file, "read", None)
            if read_method and getattr(read_method, "__call__", None):
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total += len(chunk)
                    if max_size is not None and total > max_size:
                        raise ValueError("file too large")
                    out.write(chunk)
            else:
                async for chunk in file:  # type: ignore
                    total += len(chunk)
                    if max_size is not None and total > max_size:
                        raise ValueError("file too large")
                    out.write(chunk)
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
            
        except Exception as e:
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
        total = 0
    
        try:
            with open(full_path, "wb") as out:
                read_method = getattr(file, "read", None)
                if read_method and getattr(read_method, "__call__", None):
                    while True:
                        chunk = await file.read(chunk_size)
                        if not chunk:
                            break
                        total += len(chunk)
                        if max_size is not None and total > max_size:
                            raise ValueError("file too large")
                        out.write(chunk)
                else:
                    async for chunk in file:  # type: ignore
                        total += len(chunk)
                        if max_size is not None and total > max_size:
                            raise ValueError("file too large")
                        out.write(chunk)
                out.flush()
                os.fsync(out.fileno()) 
            return str(full_path)
        except Exception as e:
            print(f"Error al guardar el archivo (async): {e}")
            raise


def get_storage(base_dir: str | Path | None = None, storage_backend: str = "nfs") -> StoragePort:
    base = base_dir or getattr(settings, "UPLOAD_PATH", "uploads")
    
    if storage_backend == "nfs":
        return NFSStore(base_dir=base)
   
    return LocalStorage(base_dir=base)