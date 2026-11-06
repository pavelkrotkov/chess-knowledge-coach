"""Build one bounded source-checked coaching pattern."""

from collections import Counter, defaultdict

from .coaching_failures_page import collect_page
from .coaching_rank import rank
from .preview_snapshot import preview_history
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence

ROW_LIMIT = 5


def build(db, learner, pair, check):
    check()
    rows, truncated = evidence(db, learner, *pair, MAX_ID, failure_only=True, limit=ROW_LIMIT)
    check()
    groups, excluded, seen = defaultdict(list), Counter(), set()
    with preview_history(db, learner) as history:
        history.targets(row["position_id"] for row in rows)
        collect_page(db, learner, history, rows, groups, excluded, seen, check=check)
        lessons = rank(db, learner, groups, history, check=check)
        check()
    return lessons, truncated, len(rows)
