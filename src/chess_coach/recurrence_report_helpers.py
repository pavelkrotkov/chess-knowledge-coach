"""Bound report history reuse and summarize its honest coverage."""

from .learner_identity import normalize_identity
from .preview_guard import require_read_snapshot
from .recurrence_sources import evidence


def target_history(db, learner, pairs, before, history):
    if history.db is not db or normalize_identity(history.learner) != normalize_identity(learner):
        raise ValueError("report history scope differs")
    require_read_snapshot(db.connection)
    history.targets(
        row["position_id"]
        for skill, operation in pairs
        for row in evidence(db, learner, skill, operation, before)[0]
    )


def update_coverage(coverage, exclusions, limited, cache):
    coverage.update(
        {
            "excluded": dict(exclusions),
            "evidence_limits_reached": limited,
            "replayed_games": len(cache),
            "sampled_decisions": sum(
                sum(bool(d["subject"]) for d in g["decisions"].values())
                for g in cache.values()
                if g
            ),
        }
    )
