"""Stage and atomically update an owner-only bounded request slot."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .opening_queue_files import MAX_BYTES, read


@contextmanager
def staged(path, value):
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(encoded) > MAX_BYTES:
        raise ValueError("private request exceeds limit")
    if path.exists() or path.is_symlink():
        read(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".opening-slot-", delete=False
        ) as f:
            temporary = Path(f.name)
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        yield temporary
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, value):
    with staged(path, value) as temporary:
        os.replace(temporary, path)
    sync(path.parent)
