"""Share an opened executable digest only during one style report."""

import hashlib
import os
from contextlib import contextmanager
from contextvars import ContextVar

CURRENT: ContextVar[dict[tuple[int, int, int, int, int], str] | None] = ContextVar(
    "style_report_engine_digests", default=None
)


@contextmanager
def report_digests():
    token = CURRENT.set({})
    try:
        yield
    finally:
        CURRENT.reset(token)


def _identity(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _current(binary, file, before):
    return _identity(os.fstat(file.fileno())) == before and _identity(binary.stat()) == before


def _digest(file):
    return hashlib.file_digest(file, "sha256").hexdigest()


def engine_digest(binary):
    with binary.open("rb") as file:
        cache = CURRENT.get()
        if cache is None:
            return _digest(file)
        before = _identity(os.fstat(file.fileno()))
        existing = cache.get(before)
        if existing is not None:
            if not _current(binary, file, before):
                raise OSError("engine changed while checking")
            return existing
        value = _digest(file)
        if not _current(binary, file, before):
            raise OSError("engine changed while hashing")
        cache[before] = value
        return value
