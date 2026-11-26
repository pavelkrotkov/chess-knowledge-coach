"""Visit the learner's exact bounded public collection and task window."""

from .capture_corpus_page import stage
from .capture_public_index import bind, task
from .capture_public_progress import PER_COLLECTION, PUBLIC_SCAN, _collection, _membership
from .capture_public_progress import initial as initial
from .deep_selection_source import learner_key


def discover(db, subject, data, building, check):
    state = building["public"]
    if state["owner"] != learner_key(subject):
        return False
    if state["collection"] is None:
        return _collection(db, subject, state, check)
    if state["checking"]:
        return _membership(db, subject, state, check)
    if state["per_collection"] >= PER_COLLECTION:
        state["collection"] = None
        return _collection(db, subject, state, check)
    row = task(db, state["collection"], state["last_task"], check)
    if row is None:
        state["collection"] = None
        return _collection(db, subject, state, check)
    state["last_task"] = row["task_id"]
    state["per_collection"] += 1
    state["scanned"] += 1
    state["done"] = state["scanned"] >= PUBLIC_SCAN
    try:
        key, candidate = bind(db, state["collection"], row["task_id"], check)
    except TimeoutError:
        building["incomplete"] = True
        raise
    except ValueError:
        return True
    stage(data, building, state["keys"], key, candidate)
    return True
