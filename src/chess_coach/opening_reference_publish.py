"""Publish a bounded immutable local opening index without replacement."""

import os
import tempfile
from pathlib import Path


def publish(directory, index_name, records, coverage, store):
    output = directory / index_name
    if output.exists() or output.is_symlink():
        raise ValueError("reference index already exists")
    if not records:
        raise ValueError("no valid reference games")
    descriptor, name = tempfile.mkstemp(prefix=".opening-reference-", dir=directory)
    os.close(descriptor)
    temporary = Path(name)
    try:
        store(temporary, records, coverage)
        if temporary.stat().st_size > 20_000_000:
            raise ValueError("reference index exceeds size limit")
        temporary.chmod(0o400)
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink()
    return coverage
