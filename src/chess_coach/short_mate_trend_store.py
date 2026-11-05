"""Bounded, atomic sidecar storage."""

import json
import os

from .fact_fingerprint import canonical, digest
from .short_mate_trend_validate import valid

MAX_BYTES = 4 * 1024 * 1024


def read(path, expected):
    if path is None:
        return None
    try:
        with path.open("rb") as file:
            raw = file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        checksum = data.pop("checksum", None)
        if checksum != digest(canonical(data)):
            return None
        return data if valid(data, expected) else None
    except (OSError, ValueError, TypeError):
        return None


def write(path, data):
    # Detect accidental edits and valid but incomplete JSON before resuming.
    raw = canonical({**data, "checksum": digest(canonical(data))}).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("trend cache exceeds limit")
    # One writer holds the pipeline lock, so a fixed temporary name cannot accumulate.
    temporary = path.with_name(path.name + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    with os.fdopen(fd, "wb") as file:
        os.fchmod(file.fileno(), 0o600)
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
