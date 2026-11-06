"""Group distinct recorded encounters without rechecking expensive sources."""

from collections import defaultdict

from .capture_compare_scope import scope
from .mastery_time import parse_utc
from .mate_assessment_rows import rows
from .related_capture_position import prompt_key


def _unmatched(row):
    return row["source_type"] == "corpus" and row["objective"] == "capture_named_target"


def select(db, subject, corpus):
    selected, limited = rows(db, subject)
    groups, seen = defaultdict(list), set()
    uncertain, unmatched = False, 0
    for row in selected:
        try:
            when = parse_utc(row["started_at"])
            uncertain |= when is None or when.isoformat() != row["started_at"]
            key = prompt_key(row["prompt_fen"])
            duplicate = key in seen
            seen.add(key)
            if duplicate:
                continue
            matched = scope(row, corpus)
            if matched:
                groups[matched["key"]].append((row, matched))
            elif _unmatched(row):
                unmatched += 1
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            uncertain = True
    return list(groups.values()), limited or uncertain, unmatched
