"""Rotate through a bounded recent window with exact material rechecks."""

from .deep_selection_source import MAX_DECISIONS
from .learner_identity import normalize_identity
from .material_fresh_order import advance, order
from .material_fresh_turn import save
from .material_fresh_validate import LIMIT as WINDOW
from .material_recent_observe import record
from .material_recent_source import eligible_color
from .pipeline_recent_rows import rows


def _positions(db, item, color, after, limit):
    # Positions store the board after the move, so the other side is to move.
    turn = " b " if color == "white" else " w "
    return db.connection.execute(
        """SELECT id,ply FROM positions WHERE game_id=? AND ply>? AND ply<=? AND instr(fen,?)>0
        ORDER BY ply LIMIT ?""",
        (item["game_id"], after, MAX_DECISIONS, turn, limit + 1),
    ).fetchall()


def _eligible(db, config, engine_hash, recent):
    subject = normalize_identity(config.learner)
    result = []
    for item in rows(db, subject, WINDOW, None)[:WINDOW]:
        recent["games_examined"] += 1
        try:
            color = eligible_color(db, subject, item, config, engine_hash)
            if color:
                result.append((item, color))
            else:
                recent["source_unavailable"] += 1
        except (ValueError, TypeError, KeyError, IndexError):
            recent["source_unavailable"] += 1
    return result


def select_recent(db, config, engine_hash, recent, limit, state):
    games = _eligible(db, config, engine_hash, recent)
    ordered, state = order(games, state)
    progress = dict(state["positions"])
    for item, color in ordered:
        after = progress[item["game_id"]]
        positions = _positions(db, item, color, after, limit)
        if not positions and after:
            positions = _positions(db, item, color, 0, limit)
        if positions:
            return item["game_id"], positions, state
    return 0, [], state


def work(db, config, engine_hash, report, outcomes, recent, scan_limit, decision_limit, state):
    recent["game_window"] = WINDOW
    game_id, positions, state = select_recent(db, config, engine_hash, recent, scan_limit, state)
    save(db, config.learner, state)
    used = set()
    for row in positions[:scan_limit]:
        if recent["processed"] >= decision_limit:
            break
        used.add(row["id"])
        state = advance(state, game_id, row["ply"])
        save(db, config.learner, state)
        record(db, config.learner, row, report, outcomes, recent)
    recent["pending"] = bool(positions)
    return used
