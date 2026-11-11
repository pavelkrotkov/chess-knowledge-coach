"""Independently verify the exact nominated opening occurrence."""

from .opening_explore_group import group


def target(db, learner, nominations, slot, budget, cache, report, limit):
    source = slot["source"]
    for key, items in nominations:
        occurrence = next((item for item in items if _matches(item, source)), None)
        if occurrence is not None:
            return _verify(db, learner, key, items, occurrence, budget, cache, report, limit)
    return None


def _verify(db, learner, key, items, target, budget, cache, report, limit):
    report["groups_checked"] += 1
    ordered = [target, *(item for item in items if item is not target)]
    branch = group(db, learner, key, ordered, budget, cache, report, limit)
    if branch is None:
        return None
    exemplar = next((item for item in branch["games"] if _matches(item, target)), None)
    if exemplar is None:
        return None
    branch["exemplar"] = exemplar
    return branch


def _matches(item, source):
    return (item["game_id"], item["position_id"]) == (source["game_id"], source["position_id"])
