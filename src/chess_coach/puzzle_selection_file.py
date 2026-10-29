"""Read a bounded project-local selection manifest for import."""

import json
from pathlib import Path

from .puzzle_selection import validate_selection


def read_selection(path, project_root, csv_sha256, archive_sha256):
    if path is None:
        return None
    root = Path(project_root).resolve(strict=True)
    source = Path(path).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError("selection manifest must be inside the project")
    try:
        with source.open("rb") as stream:
            raw = stream.read(8193)
        if len(raw) > 8192:
            raise ValueError("selection manifest is too large")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("selection manifest is invalid") from None
    return validate_selection(value, csv_sha256, archive_sha256)
