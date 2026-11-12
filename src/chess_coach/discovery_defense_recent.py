"""Scan current owned decisions from the bounded recent game window."""

from .discovery_defense_cursor import save
from .material_fresh import _select
from .material_fresh_order import advance
from .material_fresh_validate import LIMIT as WINDOW


def work(db, config, engine_hash, lane, attempt, scan_limit, decision_limit, state, used):
    lane.update(scanned=True, scan_limit=scan_limit, decision_limit=decision_limit)
    lane["game_window"] = WINDOW
    game_id, positions, state = _select(db, config, engine_hash, lane, scan_limit, state)
    save(db, config.learner, state)
    for row in positions[:scan_limit]:
        if lane["processed"] >= decision_limit:
            lane["capped"] = True
            break
        overlap = row["id"] in used
        used.add(row["id"])
        lane["examined"] += 1
        if overlap:
            lane["overlap"] += 1
        else:
            attempt(row["id"])
        state = advance(state, game_id, row["ply"])
        save(db, config.learner, state)
    if len(positions) > scan_limit and lane["examined"] == scan_limit:
        lane["capped"] = True
    return used
