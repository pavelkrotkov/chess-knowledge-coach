"""Resumable, independent, bounded game cohort selection."""

import time

from .short_mate_game_source import prepare, recheck
from .short_mate_trend_cohort import fingerprint
from .short_mate_trend_cohort import signature as source_signature


def _previous(previous):
    if not previous:
        return None
    if not previous.get("selection_complete") or len(previous["games"]) != 41:
        return previous.get("prior")
    prior = {**previous, "retained": {}}
    prior.pop("prior", None)
    return prior


def initial(key, frontier, previous):
    retained = {}
    prior = _previous(previous)
    if previous and prior is None:
        # Preserve completed work across a newly arrived game without retaining old cohorts.
        retained = dict(previous.get("retained", {}))
        retained.update({str(item["id"]): item for item in previous.get("games", [])})
        retained = dict(list(retained.items())[-41:])
    state = {
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
    if prior:
        state["prior"] = prior
    return state


def _retained_results(old, signature, identity, turns):
    if not old or old.get("signature") != signature or old.get("identity") != identity:
        return []
    expected = [turn["position_id"] for turn in turns[: len(old["results"])]]
    return old["results"] if [row[0] for row in old["results"]] == expected else []


def _item(source, signature, retained, *, retain_fields=()):
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
    item["results"] = _retained_results(old, signature, item["identity"], turns)
    if item["results"]:
        item.update({field: old.get(field) for field in retain_fields})
    return item


def _add(db, learner, game, state, seen, *, retain_fields=(), prepare_game=prepare):
    game_id = game["id"]
    # Record unavailable and duplicate rows too: either can later change the boundary.
    signature = source_signature(db, game)
    state["checked"].append([game_id, signature])
    try:
        source = prepare_game(db, learner, game_id)
        recheck(db, learner, source)
        if fingerprint(source["signature"]) != signature:
            raise ValueError("game changed")
        if source["identity"] in seen:
            state["duplicates"] += 1
        else:
            seen.add(source["identity"])
            retained = state["retained"]
            if state.get("prior"):
                retained = {str(item["id"]): item for item in state["prior"]["games"]}
            state["games"].append(_item(source, signature, retained, retain_fields=retain_fields))
    except (ValueError, TypeError, IndexError):
        state["unavailable"] += 1


def select(db, learner, games, state, deadline, *, retain_fields=(), prepare_game=prepare):
    seen = {item["identity"] for item in state["games"]}
    # The extra independent game verifies the edge of the two samples.
    while state["index"] < len(games) and len(state["games"]) < 41:
        if time.monotonic() >= deadline:
            return
        _add(
            db,
            learner,
            games[state["index"]][0],
            state,
            seen,
            retain_fields=retain_fields,
            prepare_game=prepare_game,
        )
        state["index"] += 1
    state["selection_complete"] = True
    state["retained"] = {}
    state.pop("prior", None)
