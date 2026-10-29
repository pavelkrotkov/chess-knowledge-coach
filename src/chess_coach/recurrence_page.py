"""Choose one skill pair and bind any continuation to its reporting scope."""

from .recurrence_cursor import MAX_ID, decode, encode
from .recurrence_cursor_scope import scope
from .recurrence_skills import PAIRS


def select(db, learner, begin, finish, previous, skill, operation, cursor):
    if bool(skill) != bool(operation):
        raise ValueError("select both skill and operation")
    if skill and (skill, operation) not in PAIRS:
        raise ValueError("unsupported skill and operation")
    if cursor and not skill:
        raise ValueError("a cursor requires one skill and operation")
    pairs = ((skill, operation),) if skill else PAIRS
    key = scope(
        db, learner, begin.isoformat(), finish.isoformat(), previous.isoformat(), skill, operation
    )
    before, history = decode(cursor, key) if skill else (MAX_ID, [])
    return pairs, before, history, key


def navigation(before, history, next_before, key, selected):
    return (
        links(before, history, next_before, key)
        if selected
        else {"previous": None, "next": None, "history_limit_reached": False}
    )


def links(before, history, next_before, key):
    previous = encode(history[-1], history[:-1], key) if history else None
    following = (
        encode(next_before, [*history, before], key) if next_before and len(history) < 100 else None
    )
    return {
        "previous": previous,
        "next": following,
        "history_limit_reached": bool(next_before and not following),
    }
