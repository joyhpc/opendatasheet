"""Cross-platform file locking for long-running pipeline batches."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO


class FileLock:
    """Small lock handle that keeps an exclusive file lock alive."""

    def __init__(self, path: Path, handle: TextIO, backend: str):
        self.path = path
        self.handle = handle
        self.backend = backend
        self._released = False

    def write_metadata(self, metadata: str) -> None:
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(metadata)
        self.handle.flush()

    def release(self) -> None:
        if self._released:
            return
        try:
            if self.backend == "fcntl":
                import fcntl

                fcntl.flock(self.handle, fcntl.LOCK_UN)
            elif self.backend == "msvcrt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._released = True
            self.handle.close()

    def __enter__(self) -> "FileLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def __del__(self) -> None:
        if not self._released:
            try:
                self.release()
            except Exception:
                pass


def _lock_with_fcntl(handle: TextIO) -> bool:
    try:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, BlockingIOError, OSError):
        return False


def _lock_with_msvcrt(handle: TextIO) -> bool:
    try:
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except (ImportError, OSError):
        return False


def try_exclusive_lock(path: str | os.PathLike, metadata: str | None = None) -> FileLock | None:
    """Try to acquire an exclusive non-blocking file lock.

    Returns a FileLock when successful, otherwise None. The caller must keep the
    returned object alive for as long as the lock should be held.
    """

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")

    backend = None
    if os.name == "nt":
        if _lock_with_msvcrt(handle):
            backend = "msvcrt"
    else:
        if _lock_with_fcntl(handle):
            backend = "fcntl"

    if backend is None:
        handle.close()
        return None

    lock = FileLock(lock_path, handle, backend)
    if metadata is not None:
        lock.write_metadata(metadata)
    return lock
