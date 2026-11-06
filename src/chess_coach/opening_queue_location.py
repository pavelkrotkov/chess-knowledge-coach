"""Find the owner-only project directory and bind the current database."""

from pathlib import Path

from .tactical_study_path import planning


def location(db, root, learner):
    if not root:
        raise ValueError("private planning unavailable")
    root = Path(root).resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    database = Path(db.path).resolve(strict=True)
    if not data.is_relative_to(root) or not database.is_relative_to(data):
        raise ValueError("database outside private project")
    directory, _ = planning(root, learner)
    info = database.stat()
    return directory, [str(database), info.st_dev, info.st_ino]
