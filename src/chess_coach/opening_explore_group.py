"""Verify a bounded set of occurrences for one nominated branch."""

import time

from .opening_explore_verify import verify
from .tactical_course_budget import PreviewUnavailable


def group(db, learner, key, items, budget, cache, report, check_limit):
    verified = []
    identities = set()
    # Reserve at least two checks for each remaining group in the shortlist.
    allowance = min(3, check_limit - report["occurrences_checked"])
    for item in items[:allowance]:
        if time.monotonic() >= budget.expires:
            report["partial"] = True
            break
        report["occurrences_checked"] += 1
        found = _verify(db, learner, key, item, budget, cache, report)
        if found is None:
            continue
        if found["game_key"] in identities:
            report["duplicates"] += 1
            continue
        identities.add(found["game_key"])
        verified.append(found)
    if len(items) > allowance:
        report["partial"] = True
    return _branch(key, items, verified)


def _branch(key, items, verified):
    if len(verified) < 2:
        return None
    exemplar = next((item for item in verified if item["catalog"]["items"]), None)
    if exemplar is None:
        return None
    return {
        "color": key[0],
        "position": key[1],
        "nominated": len(items),
        "games": verified,
        "exemplar": exemplar,
    }


def _verify(db, learner, key, item, budget, cache, report):
    try:
        return verify(db, learner, key, item, budget, cache)
    except PreviewUnavailable:
        report["deferred"] += 1
        report["partial"] = True
    except (ValueError, TypeError, KeyError, IndexError):
        report["unavailable"] += 1
    return None
