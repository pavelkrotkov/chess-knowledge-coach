"""Select bounded, source-checked recurring tactical patterns."""

from collections import Counter, defaultdict

from .coaching_failures_page import collect_page
from .coaching_rank import rank
from .preview_snapshot import preview_history
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .tactical_course_deadline import PreviewDeadline

PAIRS = (
    ("hanging_piece", "execute"),
    ("hanging_piece", "prevent"),
    ("mate_in_one", "execute"),
    ("calculation", "execute"),
)
CURRENT_PAIRS = (*PAIRS, ("fork", "execute"))
PER_PAIR = 12
BATCH_SIZE = 2


def _collect(db, subject, rows, budget):
    groups, excluded, seen = defaultdict(list), Counter(), set()
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        with budget.scope(snapshot=True), preview_history(db, subject) as history:
            history.targets(row["position_id"] for row in batch)
            collect_page(db, subject, history, batch, groups, excluded, seen)
    return groups, excluded


def _pair(db, subject, skill, operation, budget):
    with budget.scope(snapshot=True):
        rows, truncated = evidence(
            db, subject, skill, operation, MAX_ID, failure_only=True, limit=PER_PAIR
        )
        limited = truncated or len(rows) > PER_PAIR
        rows = rows[:PER_PAIR]
    groups, excluded = _collect(db, subject, rows, budget)
    with budget.scope(snapshot=True), preview_history(db, subject) as history:
        history.targets(row["position_id"] for row in rows)
        items = rank(db, subject, groups, history)
    return items, {
        "skill": skill,
        "operation": operation,
        "examined": len(rows),
        "limited": limited,
        "excluded": dict(excluded),
        "status": "complete",
    }


def candidates(db, subject, budget, *, pairs=CURRENT_PAIRS):
    groups, coverage = [], []
    for skill, operation in pairs:
        try:
            items, stats = _pair(db, subject, skill, operation, budget)
        except PreviewDeadline:
            budget.check()
            items = []
            stats = {
                "skill": skill,
                "operation": operation,
                "examined": None,
                "limited": True,
                "excluded": {},
                "status": "deferred: time budget",
            }
        groups.extend(items)
        coverage.append(stats)
    groups.sort(
        key=lambda item: (
            -item["miss_games"],
            item["lesson"]["skill"],
            item["lesson"]["operation"],
            item["lesson"]["family"],
        )
    )
    return groups, coverage
