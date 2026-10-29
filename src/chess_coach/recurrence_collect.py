"""Collect a bounded set of attributable recorded candidates."""

from collections import Counter

from .recurrence_recorded import new_groups, record, result
from .recurrence_selection import consider
from .recurrence_sources import PAIRS, evidence


def collect(db, learner, sources, begin, finish, previous):
    excluded, cache, parts, found, limited = Counter(), {}, {}, [], []
    recorded = new_groups()
    for skill, operation in PAIRS:
        rows, truncated = evidence(db, learner, skill, operation)
        record(rows, sources, begin, finish, previous, recorded)
        if truncated:
            limited.append(f"{skill}.{operation}")
        for row in rows:
            item = consider(
                db, learner, row, sources, cache, parts, excluded, begin, finish, previous
            )
            if item:
                found.append(item)
    return found, excluded, limited, cache, result(recorded)


def deduplicate(found, excluded):
    selected, seen = [], set()
    for item in found:
        key = (item["game_key"], item["ply"], item["skill"], item["operation"], item["family"])
        if key in seen:
            excluded["duplicate decision"] += 1
        else:
            seen.add(key)
            selected.append(item)
    return selected
