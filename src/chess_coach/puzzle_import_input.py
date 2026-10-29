"""Validate a project-local CSV snapshot and serialize import invocations."""

import re
from pathlib import Path

from .puzzle_csv import _checksum


def snapshot_path(path: str | Path, project_root: str | Path) -> Path:
    root = Path(project_root).resolve(strict=True)
    source = Path(path).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file() or source.suffix.lower() != ".csv":
        raise ValueError("decoded CSV must be a regular file inside the project")
    return source


def check_digest(value: str | None) -> None:
    if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("digest must be lowercase SHA-256")


def verify_snapshot(path: Path, digest: str) -> None:
    if _checksum(path) != digest:
        raise ValueError("decoded CSV checksum does not match")
