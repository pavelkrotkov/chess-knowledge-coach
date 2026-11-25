"""Revalidate one owner-selected context before planning."""

from .opening_context_launch_preflight import preflight
from .opening_context_launch_scope import cursor as cursor_scope
from .opening_context_launch_token import context as read_context


def _choice(db, prior, choice, cursor):
    if prior is None:
        if cursor and choice:
            raise ValueError("opening selection scope changed")
        return choice
    if choice and choice != prior[2]:
        raise ValueError("opening selection changed")
    if cursor and prior[4] != cursor_scope(db, cursor, prior[1]):
        raise ValueError("opening window changed")
    return prior[2]


def before(db, root, subject, choice, selected_token, cursor):
    prior = read_context(db, subject, selected_token) if selected_token else None
    choice = _choice(db, prior, choice, cursor)
    if not choice:
        return None
    current = preflight(db, root, subject, choice)
    if prior is not None and current["binding"] != prior[3]:
        raise ValueError("opening context changed")
    return current
