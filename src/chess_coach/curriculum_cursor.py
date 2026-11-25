"""Encode bounded continuation state and reject changed source scope."""

from datetime import datetime

from .db import Database
from .fact_fingerprint import digest
from .mastery_time import parse_utc


def new_state(
    db: Database, learner: str, version: str, limit: int, scan_limit: int, now: datetime
) -> dict:
    from .curriculum_canonical_cursor import fields as canonical_fields
    from .curriculum_prerequisite_source import POLICY, graph
    from .curriculum_public_cursor import fields

    return {
        **fields(),
        **canonical_fields(),
        "v": 6,
        "prerequisite_policy": POLICY,
        "prerequisite_graph": graph(),
        "prerequisite_scope": None,
        "prerequisite_checked": False,
        "prerequisite_offered": False,
        "prerequisite_deferred": False,
        "subject_hash": digest(learner),
        "corpus_version": version,
        "limit": limit,
        "scan_limit": scan_limit,
        "as_of": now.isoformat(),
        "revision": revision(db),
        "phase": "due",
        "capture_pending": None,
        "fork_pending": None,
        "family_turn": now.date().toordinal() % 4,
        "family_index": 0,
        "due_after": None,
        "new_after": None,
        "pending": None,
        "scheduled_after": 0,
        "scheduled_best": 0,
        "seen": [],
    }


def revision(db: Database) -> int:
    return db.connection.execute(
        "SELECT revision FROM curriculum_source_revision WHERE id=1"
    ).fetchone()[0]


def resume_state(
    db: Database,
    state: dict,
    learner: str,
    version: str,
    limit: int,
    scan_limit: int,
    as_of: datetime | None,
) -> tuple[dict, datetime]:
    if (state["subject_hash"], state["corpus_version"], state["limit"], state["scan_limit"]) != (
        digest(learner),
        version,
        limit,
        scan_limit,
    ):
        raise ValueError("curriculum cursor scope changed; restart the plan")
    now = parse_utc(state["as_of"])
    if now is None or (as_of is not None and now != as_of):
        raise ValueError("curriculum cursor time changed; restart the plan")
    if state["revision"] != revision(db):
        raise ValueError("curriculum sources changed; restart the plan")
    if state["v"] in {4, 5, 6, 8}:
        from .curriculum_prerequisite_source import POLICY, graph

        if (state["prerequisite_policy"], state["prerequisite_graph"]) != (POLICY, graph()):
            raise ValueError("curriculum prerequisite policy changed; restart the plan")
    return state, now
