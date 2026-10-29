"""Collect a bounded set of attributable recorded candidates."""

from collections import Counter

from .recurrence_recorded import new_groups, record, result
from .recurrence_scan import scan
from .recurrence_sources import evidence


def collect(db, learner, sources, begin, finish, previous, pairs, before):
    excluded, cache, parts, found, limited = Counter(), {}, {}, [], []
    recorded, next_before = new_groups(), None
    for skill, operation in pairs:
        rows, truncated = evidence(db, learner, skill, operation, before)
        record(rows, sources, begin, finish, previous, recorded)
        if truncated:
            limited.append(f"{skill}.{operation}")
        next_before = scan(
            db,
            learner,
            rows,
            sources,
            cache,
            parts,
            excluded,
            found,
            begin,
            finish,
            previous,
            single=len(pairs) == 1,
        )
        if len(pairs) == 1 and truncated and next_before is None:
            next_before = rows[-1]["id"]
    return found, excluded, limited, cache, result(recorded), next_before


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
