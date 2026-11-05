"""Select bounded, source-checked recurring tactical patterns."""

from collections import Counter, defaultdict

from .coaching_failures_page import collect_page
from .coaching_rank import rank
from .preview_snapshot import preview_history
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence

PAIRS = (
    ("hanging_piece", "execute"),
    ("hanging_piece", "prevent"),
    ("mate_in_one", "execute"),
    ("calculation", "execute"),
)
PER_PAIR = 12


def _pair(db, subject, skill, operation):
    rows, truncated = evidence(
        db, subject, skill, operation, MAX_ID, failure_only=True, limit=PER_PAIR
    )
    limited = truncated or len(rows) > PER_PAIR
    rows = rows[:PER_PAIR]
    groups, excluded = defaultdict(list), Counter()
    with preview_history(db, subject) as history:
        history.targets(row["position_id"] for row in rows)
        collect_page(db, subject, history, rows, groups, excluded, set())
        candidates = rank(db, subject, groups, history)
    return candidates, {
        "skill": skill,
        "operation": operation,
        "examined": len(rows),
        "limited": limited,
        "excluded": dict(excluded),
    }


def candidates(db, subject, budget):
    groups, coverage = [], []
    for skill, operation in PAIRS:
        with budget.scope(snapshot=True):
            items, stats = _pair(db, subject, skill, operation)
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
