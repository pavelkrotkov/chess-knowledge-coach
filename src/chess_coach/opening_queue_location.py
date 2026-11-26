"""Find the owner-only project directory and bind the current database."""

from pathlib import Path

from .tactical_study_path import planning


def scope(db, root, previous=None):
    """Validate the explicit project and database shared by private readers."""
    if root is None:
        return previous
    selected = Path(root).resolve(strict=True)
    data = (selected / ".runtime" / "data").resolve(strict=True)
    database = Path(db.path).resolve(strict=True)
    if (
        previous not in (None, selected)
        or not data.is_relative_to(selected)
        or not database.is_relative_to(data)
        or not database.is_file()
    ):
        raise ValueError("database outside private project")
    return selected


def location(db, root, learner):
    selected = scope(db, root)
    if selected is None:
        raise ValueError("private planning unavailable")
    directory, _ = planning(selected, learner)
    database = Path(db.path).resolve(strict=True)
    info = database.stat()
    return directory, [str(database), info.st_dev, info.st_ino]
