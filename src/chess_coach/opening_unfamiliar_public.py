"""Bind the public line and profile to one unchanged private index."""

from .opening_course_public import _identity, continuation
from .opening_profile_index import INDEX_NAME
from .opening_profile_read import _private_file, profile
from .tactical_study_path import planning


def public(root, subject, parent, move, budget):
    budget.check()
    try:
        directory, _ = planning(root, subject)
        path = directory / INDEX_NAME
        if not _private_file(path, directory):
            return None
        before = _identity(path)
        line, _status = continuation(root, subject, parent, move, None, expires=budget.expires)
        budget.check()
        data = profile(root, subject, parent, move, expires=budget.expires) if line else None
        budget.check()
        if not _private_file(path, directory) or _identity(path) != before:
            return None
        if data and data["games"]:
            return line, data
    except (OSError, ValueError, TypeError):
        pass
    finally:
        budget.check()
    return None
