"""Isolate purpose-only scheduling preflight from normal work."""


def sequence_or_none(db, learner, lookup):
    try:
        return lookup(db, learner)[1]
    except Exception:
        return None
