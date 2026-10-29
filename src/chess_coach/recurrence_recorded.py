"""Count bounded recorded mappings separately from verified game samples."""

from collections import Counter, defaultdict

from .mastery_time import parse_utc


def period(value, begin, finish, previous):
    when = parse_utc(value)
    if when is None:
        return "unknown date"
    if not previous <= when < finish:
        return "outside window"
    return "current" if when >= begin else "previous"


def record(rows, sources, begin, finish, previous, groups):
    for row in rows:
        selected = period(row["observation_at"], begin, finish, previous)
        if selected in {"unknown date", "outside window"}:
            continue
        if row["game_id"] is None or row["mapping_status"] != "active":
            continue
        if row["review_decision"] in {"reject", "revoke"}:
            continue
        groups[(selected, row["skill"], row["operation"])][row["outcome"]] += 1


def result(groups):
    return [
        {"period": period, "skill": skill, "operation": operation, "rows": dict(counts)}
        for (period, skill, operation), counts in sorted(groups.items())
    ]


def new_groups():
    return defaultdict(Counter)
