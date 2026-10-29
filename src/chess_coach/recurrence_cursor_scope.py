"""Identify the learner and query scope to which a cursor belongs."""

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity


def scope(db, learner, start, end, previous, skill, operation):
    return digest(
        canonical(
            [
                str(db.path.resolve()),
                normalize_identity(learner),
                start,
                end,
                previous,
                skill,
                operation,
            ]
        )
    )
