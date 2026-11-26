"""Advance one owner-bound public collection and familiarity cursor."""

from .capture_public_index import collection, game
from .deep_selection_source import learner_key
from .related_capture_public import _game_id

COLLECTIONS = 100
PER_COLLECTION = 100
PUBLIC_SCAN = 500


def initial(subject):
    return {
        "owner": learner_key(subject),
        "last_collection": "",
        "collection": None,
        "game": None,
        "game_after": 0,
        "checking": False,
        "collections": 0,
        "last_task": "",
        "per_collection": 0,
        "scanned": 0,
        "keys": [],
        "done": False,
    }


def _collection(db, subject, state, check):
    if state["collections"] >= COLLECTIONS or state["scanned"] >= PUBLIC_SCAN:
        state["done"] = True
        return False
    row = collection(db, state["last_collection"], check)
    if row is None:
        state["done"] = True
        return False
    state["last_collection"] = row["version"]
    state["collections"] += 1
    game_id = _game_id(row["source_url"])
    state.update(
        collection=row["version"],
        last_task="",
        per_collection=0,
        game=game_id,
        game_after=0,
        checking=bool(game_id),
    )
    return True


def _membership(db, subject, state, check):
    row = game(db, subject, state["game"], state["game_after"], check)
    if row is None:
        state["checking"] = False
    elif row["familiar"]:
        state.update(collection=None, checking=False)
    else:
        state["game_after"] = row["id"]
    return True
