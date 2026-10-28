"""Discover production Python files without hiding analysis errors."""

from __future__ import annotations

import os
from pathlib import Path


def source_directories(root: Path, current: Path, names: list[str]) -> list[str]:
    excluded = {".git", ".venv", "__pycache__"}
    if current == root:
        excluded.update({"tests", ".runtime"})
    return [name for name in names if name not in excluded]


def production_files(root: Path) -> list[Path]:
    required = [root / "src/chess_coach/__init__.py", root / "scripts/quality.py"]
    if not all(path.is_file() for path in required):
        raise ValueError("missing production source directory or quality checker")
    files = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, names, filenames in os.walk(root, onerror=raise_walk_error):
        current = Path(directory)
        names[:] = source_directories(root, current, names)
        files.extend(current / name for name in filenames if name.endswith(".py"))
    files.sort()
    validate_files(root, files, required)
    return files


def validate_files(root: Path, files: list[Path], required: list[Path]) -> None:
    package_files = [path for path in files if path.parent == root / "src/chess_coach"]
    if len(package_files) < 2 or any(path not in files for path in required):
        raise ValueError("missing production source files")
