"""Validate the scope and bounds of a curriculum cursor."""

from .curriculum_cursor_values import integer, text


def validate_scope(state: dict) -> None:
    _identity(state)
    _bounds(state)
    if not integer(state["revision"], 0, 2**63 - 1):
        raise ValueError("invalid revision")
    if state["phase"] not in {"due", "new"}:
        raise ValueError("invalid phase")


def _identity(state: dict) -> None:
    if not text(state["subject_hash"], 64) or len(state["subject_hash"]) != 64:
        raise ValueError("invalid subject")
    if not text(state["corpus_version"], 256) or not text(state["as_of"], 64):
        raise ValueError("invalid scope")


def _bounds(state: dict) -> None:
    if not integer(state["limit"], 1, 50) or not integer(state["scan_limit"], 1, 1000):
        raise ValueError("invalid bounds")
