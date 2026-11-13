"""Bound a group of opening selections to one learner and public source."""

from .opening_course_public import _identity
from .opening_profile_index import INDEX_NAME
from .opening_profile_read import _private_file
from .tactical_study_path import planning


def _index(root, subject):
    directory, _ = planning(root, subject)
    path = directory / INDEX_NAME
    if not _private_file(path, directory):
        raise ValueError("public index unavailable")
    return path, _identity(path)


def start(db, root, subject):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    path, identity = _index(root, subject)
    return version, path, identity


def check(db, root, subject, guard, budget):
    budget.check()
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != guard[0]:
        raise ValueError("opening source changed")
    if _index(root, subject) != (guard[1], guard[2]):
        raise ValueError("public index changed")
