"""Bound automatic course exports and reserve project storage."""

import json
import re
import shutil
import subprocess
import time

from .tactical_export_input import MAX_BYTES, load
from .tactical_study_preview import preview

PREFIX = "tactical-auto-"
MAX_FILES = 8
PROJECT_LIMIT = 10 * 1024**3
RESERVE = 8 * 1024**2


def output(root, directory, result, budget):
    """Reuse a verified digest or reserve space for a new immutable export."""
    with budget.scope(snapshot=False):
        path, needed = _select(root, directory, result)
    if needed:
        # Check allocation after building and just before creating another file.
        _reserve(root, budget.expires - time.monotonic())
        budget.check()
    return path, needed


def _select(root, directory, result):
    version = result["export_sha256"]
    path = directory / f"{PREFIX}{version}.json"
    # A digest name is only a hint until the full saved envelope is checked.
    if path.exists() or path.is_symlink():
        existing = load(root, path)
        preview(existing, version)
        if existing != result:
            raise ValueError("saved course differs")
        return path, False
    if len(json.dumps(result, sort_keys=True, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError("course exceeds limit")
    files = [
        p for p in directory.iterdir() if re.fullmatch(r"tactical-auto-[0-9a-f]{64}\.json", p.name)
    ]
    if len(files) >= MAX_FILES:
        raise ValueError("automatic course archive is full")
    return path, True


def _reserve(root, remaining):
    """Check project allocation and disk reserve within the remaining budget."""
    usage = subprocess.run(
        ["du", "-skx", str(root)],
        check=True,
        capture_output=True,
        text=True,
        timeout=min(8, max(0.001, remaining)),
    )
    allocated = int(usage.stdout.split()[0]) * 1024
    if allocated + RESERVE > PROJECT_LIMIT or shutil.disk_usage(root).free < RESERVE:
        raise ValueError("course storage reserve unavailable")
