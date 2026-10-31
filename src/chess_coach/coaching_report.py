"""Build a provisional, source-linked coaching preview from repeated failures."""

from collections import Counter, defaultdict

from .coaching_failures_page import collect_page
from .coaching_rank import rank
from .learner_identity import normalize_identity
from .preview_snapshot import preview_history
from .recurrence_cursor import MAX_ID
from .recurrence_skills import PAIRS
from .recurrence_snapshot import read_snapshot
from .recurrence_sources import evidence, games

VERSION = "coaching-preview-v1"


def report(db, subject):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    with read_snapshot(db), preview_history(db, learner) as history:
        groups, limits = collect(db, learner, history)
        _, coverage = games(db, learner)
        coverage["database_games"] = db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[
            0
        ]
        coverage["database_analysis"] = dict(
            db.connection.execute(
                "SELECT status, COUNT(*) FROM pipeline_stages WHERE stage=? GROUP BY status",
                ("analysis",),
            ).fetchall()
        )
        lessons = rank(db, learner, groups, history)
    return {
        "kind": VERSION,
        "skill": "Coaching preview",
        "operation": "recurring patterns",
        "groups": lessons[:3],
        "eligible_groups": len(lessons),
        "coverage": coverage,
        **limits,
    }


def collect(db, learner, history):
    pages, limited = [], []
    for skill, operation in PAIRS:
        rows, truncated = evidence(db, learner, skill, operation, MAX_ID, failure_only=True)
        pages.append((skill, operation, rows))
        if truncated:
            limited.append(f"{skill}.{operation}")
    history.targets(row["position_id"] for _, _, rows in pages for row in rows)
    groups, excluded = defaultdict(list), Counter()
    seen = set()
    for _, _, rows in pages:
        collect_page(db, learner, history, rows, groups, excluded, seen)
    return groups, {"failure_limits": limited, "excluded": dict(excluded)}
