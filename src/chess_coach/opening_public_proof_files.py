"""Retain a few immutable private preparations without replacing earlier results."""

import os

from .fact_fingerprint import canonical, digest
from .opening_queue_files import read
from .opening_queue_write import staged, sync

ATTEMPTS = 3


def _path(directory, key, attempt, *, prefix="opening-public-proof"):
    return directory / f"{prefix}-{key}-{attempt}.json"


def _checked(value, key):
    if (
        not isinstance(value, dict)
        or value.get("binding") != key
        or not isinstance(value.get("payload"), dict)
        or value.get("sha256") != digest(canonical(value["payload"]))
    ):
        raise ValueError("public preparation unavailable")
    return value["payload"]


# An existing prepared result is immutable and hash-checked before it is used.
def latest(directory, key, *, prefix="opening-public-proof"):
    for attempt in reversed(range(ATTEMPTS)):
        value = read(_path(directory, key, attempt, prefix=prefix))
        if value is not None:
            path = _path(directory, key, attempt, prefix=prefix)
            if path.stat().st_mode & 0o777 != 0o400:
                raise ValueError("public preparation is not immutable")
            return _checked(value, key)
    return None


# Recheck source and deadline after fsync, immediately before the no-replace link.
def publish(directory, key, payload, confirm, *, prefix="opening-public-proof"):
    previous = latest(directory, key, prefix=prefix)
    if previous == payload:
        confirm()
        return
    value = {"binding": key, "payload": payload, "sha256": digest(canonical(payload))}
    for attempt in range(ATTEMPTS):
        path = _path(directory, key, attempt, prefix=prefix)
        if path.exists() or path.is_symlink():
            continue
        with staged(path, value) as temporary:
            temporary.chmod(0o400)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            confirm()
            os.link(temporary, path)
        sync(directory)
        return
    raise ValueError("public preparation limit reached")
