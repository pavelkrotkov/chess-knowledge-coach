"""Reject symlinked snapshot path components before filesystem access."""

from pathlib import Path


def checked_path(path, root):
    """Reject existing symlink components before touching project artifacts."""
    path = Path(path)
    root = Path(root)
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        raise ValueError("snapshot must remain inside project root") from None
    current = root
    if current.is_symlink():
        raise ValueError("snapshot path contains a symlink")
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("snapshot path contains a symlink")
    return path
