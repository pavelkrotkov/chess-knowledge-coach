"""Resumable, independent, bounded game cohort selection."""

import time

from .short_mate_game_source import _signature, prepare, recheck
from .short_mate_trend_cohort import fingerprint


def initial(key, frontier, previous):
    retained = {}
    if previous:
        # Preserve completed work across a newly arrived game without retaining old cohorts.
        retained = dict(previous.get("retained", {}))
        retained.update({str(item["id"]): item for item in previous.get("games", [])})
        retained = dict(list(retained.items())[-41:])
    return {
        "binding": key,
        "frontier": frontier,
        "checked": [],
        "games": [],
        "retained": retained,
        "index": 0,
        "unavailable": 0,
        "duplicates": 0,
        "selection_complete": False,
    }


def _item(source, signature, retained):
    turns = [context for context, _ in source["pairs"] if context["subject"]]
    item = {
        "id": source["game_id"],
        "date": source["started_at"],
        "identity": source["identity"],
        "signature": signature,
        "eligible": len(turns),
        "results": [],
    }
    old = retained.get(str(source["game_id"]))
    # A changed input or a different independent game invalidates every old outcome.
    if old and old.get("signature") == signature and old.get("identity") == item["identity"]:
        item["results"] = old["results"]
    return item


def _add(db, learner, game, state, seen):
    game_id = game["id"]
    # Record unavailable and duplicate rows too: either can later change the boundary.
    signature = fingerprint(_signature(db, game))
    state["checked"].append([game_id, signature])
    try:
        source = prepare(db, learner, game_id)
        recheck(db, learner, source)
        if fingerprint(source["signature"]) != signature:
            raise ValueError("game changed")
        if source["identity"] in seen:
            state["duplicates"] += 1
        else:
            seen.add(source["identity"])
            state["games"].append(_item(source, signature, state["retained"]))
    except (ValueError, TypeError, IndexError):
        state["unavailable"] += 1


def select(db, learner, games, state, deadline):
    seen = {item["identity"] for item in state["games"]}
    # The extra independent game verifies the edge of the two samples.
    while state["index"] < len(games) and len(state["games"]) < 41:
        if time.monotonic() >= deadline:
            return
        _add(db, learner, games[state["index"]][0], state, seen)
        state["index"] += 1
    state["selection_complete"] = True
    state["retained"] = {}
