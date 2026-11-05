"""Observe a small, restartable portion of one recent analyzed game."""

from .material_recent_cursor import save
from .material_recent_observe import observe
from .material_recent_select import choose
from .material_recent_state import finished


def work(db, config, engine_hash, state, report, outcomes, recent, scan_limit, decision_limit):
    item, state = choose(db, config, engine_hash, state, recent)
    if item is None:
        recent["pending"] = False
        return state, set()
    rows = db.connection.execute(
        "SELECT id,ply FROM positions WHERE game_id=? AND ply>? ORDER BY ply LIMIT ?",
        (item["game_id"], state["ply"], scan_limit + 1),
    ).fetchall()
    used, scanned = set(), 0
    for row in rows[:scan_limit]:
        if recent["processed"] >= decision_limit:
            break
        used.add(row["id"])
        scanned += 1
        state = observe(db, config.learner, row, state, report, outcomes, recent)
    if scanned == len(rows):
        state = finished(state)
        save(db, config.learner, state)
    recent["pending"] = bool(state["within"] or state["after"])
    return state, used
