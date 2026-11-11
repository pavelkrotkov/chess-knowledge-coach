"""Spend remaining bounded checks on the slot's exact nominated occurrence."""

import time

from .opening_explore_latest_target import target


def more(db, learner, nominations, slot, budget, cache, report, groups, limit):
    if not report["branch"] or not slot or report["groups_checked"] >= groups:
        return
    if report["occurrences_checked"] + 2 > limit or time.monotonic() >= budget.expires:
        report["partial"] = True
        return
    remaining = nominations[report["groups_checked"] :]
    report["_latest_candidate"] = target(db, learner, remaining, slot, budget, cache, report, limit)
