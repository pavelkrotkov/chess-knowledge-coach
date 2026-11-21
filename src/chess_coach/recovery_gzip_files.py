"""Stage and publish distinct, non-overwriting recovery artifacts."""

import hashlib
import os
import tempfile
from pathlib import Path

from .recovery import _publish


def temporary(target):
    descriptor, name = tempfile.mkstemp(prefix=".chess-recovery-", dir=target.parent)
    os.close(descriptor)
    return Path(name)


def sync(path):
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def discard(published):
    for staged, target in published:
        if target.exists() and os.path.samefile(staged, target):
            target.unlink()


def publish(temporary, targets, published):
    for staged, target in zip(temporary, targets, strict=True):
        _publish(staged, target)
        published.append((staged, target))


def digest_file(path, deadline):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            deadline.check()
            digest.update(chunk)
    return digest.hexdigest()
