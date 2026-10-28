"""Validate project-contained source and new destination paths."""

from pathlib import Path


def recovery_paths(
    source: str | Path, destination: str | Path, project_root: str | Path
) -> tuple[Path, Path]:
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project root must be an existing directory")
    try:
        source_path = Path(source).resolve(strict=True)
    except FileNotFoundError:
        raise ValueError("source database does not exist") from None
    target = _new_target(destination)
    if not source_path.is_relative_to(root) or not target.is_relative_to(root):
        raise ValueError("source and destination must be within the selected project root")
    if not source_path.is_file():
        raise ValueError("source database must be an existing regular file")
    return source_path, target


def _new_target(destination: str | Path) -> Path:
    destination_input = Path(destination)
    if destination_input.name in {"", ".", ".."}:
        raise ValueError("destination must name a new file")
    parent = destination_input.parent.resolve(strict=True)
    target = parent / destination_input.name
    if target.exists() or target.is_symlink():
        raise FileExistsError("destination already exists")
    ensure_no_companions(target)
    return target


def ensure_no_companions(target: Path) -> None:
    for suffix in ("-journal", "-wal", "-shm"):
        companion = Path(str(target) + suffix)
        if companion.exists() or companion.is_symlink():
            raise FileExistsError("destination SQLite companion already exists")
