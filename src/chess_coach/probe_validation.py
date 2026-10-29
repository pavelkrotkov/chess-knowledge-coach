"""Validate idempotent probe event requests."""


def validate(event_id, kind, answer):
    if not isinstance(event_id, str) or not 0 < len(event_id) <= 256:
        raise ValueError("invalid event")
    if kind not in {"answer", "hint", "reveal"} or (kind == "answer") != isinstance(answer, str):
        raise ValueError("invalid request")
    if answer is not None and not 0 < len(answer.strip()) <= 32:
        raise ValueError("invalid answer")
