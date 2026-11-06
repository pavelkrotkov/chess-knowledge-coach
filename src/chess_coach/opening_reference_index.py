"""Publish one separate, immutable local index of reference positions."""

import os
import tempfile
from pathlib import Path

from .opening_reference_games import collect
from .opening_reference_source import SOURCE_NAME, read
from .opening_reference_store import store as _store
from .tactical_study_path import planning

INDEX_NAME = "opening-reference-broadcast-2026-09-v1.sqlite"


def build(root, subject):
    directory, _ = planning(root, subject)
    source = directory / SOURCE_NAME
    if source.is_symlink() or source.resolve(strict=True).parent != directory:
        raise ValueError("reference source unavailable")
    output = directory / INDEX_NAME
    if output.exists() or output.is_symlink():
        raise ValueError("reference index already exists")
    text, truncated = read(source)
    records, coverage = collect(text, truncated)
    if not records:
        raise ValueError("no valid reference games")
    descriptor, name = tempfile.mkstemp(prefix=".opening-reference-", dir=directory)
    os.close(descriptor)
    temporary = Path(name)
    try:
        _store(temporary, records, coverage)
        if temporary.stat().st_size > 20_000_000:
            raise ValueError("reference index exceeds size limit")
        temporary.chmod(0o400)
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink()
    return coverage
