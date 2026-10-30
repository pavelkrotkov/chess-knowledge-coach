"""Persist one deterministic recent-game scheduling cycle."""

from .deep_selection_source import learner_key
from .fact_fingerprint import canonical
from .style_protection_schedule_discover import HISTORY_LIMIT, discover
from .style_protection_schedule_store import insert as insert_protection
from .style_schedule_budget import CURRENT
from .style_schedule_candidates import allocate
from .style_schedule_rotation import advance
from .style_schedule_schema import validate_style_schedule
from .style_schedule_slots import insert_slot
from .style_schedule_slots import pending as pending
from .style_schedule_slots import update_slot as update_slot


def next_sequence(db, learner):
    validate_style_schedule(db.connection)
    key = learner_key(learner)
    row = db.connection.execute(
        "SELECT COALESCE(MAX(sequence),-1)+1 FROM style_schedule_cycles WHERE learner_key=?",
        (key,),
    ).fetchone()
    return key, row[0]


def create_cycle(db, learner):
    key, sequence = next_sequence(db, learner)
    budget = CURRENT.get()
    if budget is None:
        raise RuntimeError("scheduling requires a history budget")
    original_limit = budget["limit"]
    budget["limit"] = min(original_limit, budget["used"] + 500)
    try:
        coverage, slots, candidates = allocate(db, learner, key, sequence)
    finally:
        budget["limit"] = original_limit
    before_protection = budget["used"]
    candidate, binding, reason, used = discover(db, learner, key, candidates, slots, budget)
    coverage["protection_history_units"] = used
    coverage["protection_history_unit_limit"] = HISTORY_LIMIT
    coverage["scan_history_units"] = before_protection
    coverage["scan_history_unit_limit"] = 500
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        cursor = db.connection.execute(
            "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
            (key, sequence, canonical(coverage)),
        )
        slot_ids = {}
        for kind, item in slots:
            slot_ids[kind] = insert_slot(db, cursor.lastrowid, kind, item)
            if item is not None:
                advance(db, key, kind, item["game_id"])
        insert_protection(db, cursor.lastrowid, key, candidate, binding, reason, slot_ids, slots)
        db.connection.commit()
        return cursor.lastrowid
    except BaseException:
        db.connection.rollback()
        raise
