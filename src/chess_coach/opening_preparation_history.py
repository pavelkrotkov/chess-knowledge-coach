"""Check a bounded sample of same-side, owner-verified game history."""

from .analysis_positions import decisions
from .opening_decision_budget import MAX_GAME_BYTES, MAX_POSITIONS
from .opening_preparation_graph import _key
from .opening_storage import position_key
from .style_schedule_budget import LIMIT as HISTORY_LIMIT
from .style_time_candidates import recent_games
from .style_time_projection import VERSION as TIME_VERSION

MAX_GAMES = 20


def _bounded(connection, game):
    return not connection.execute(
        "SELECT 1 FROM positions WHERE game_id=? LIMIT 1 OFFSET ?",
        (game["id"], MAX_POSITIONS),
    ).fetchone()


def _observed(connection, game):
    positions, edges = set(), set()
    for row, board in decisions(connection, game):
        if not board.is_valid():
            raise ValueError("game history unavailable")
        parent = position_key(board)
        replay = board.copy()
        replay.push_uci(row["uci"])
        child = position_key(replay)
        positions.update((_key(parent), _key(child)))
        edges.add(_key([parent, row["uci"], child]))
    return positions, edges


def _checked_game(connection, game):
    if not _bounded(connection, game):
        return None
    try:
        return _observed(connection, game)
    except ValueError:
        return None


# An observed move belongs to the checked game, not necessarily the learner.
# Missing metadata or any skipped game prevents a negative coverage claim.
def coverage(db, learner, color, graph):
    games, flags = recent_games(db, learner, limit=MAX_GAMES, max_game_bytes=MAX_GAME_BYTES)
    positions, edges, checked, skipped = set(), set(), 0, 0
    for game, side in games:
        if side != color:
            continue
        observed = _checked_game(db.connection, game)
        if observed is None:
            skipped += 1
            continue
        positions.update(observed[0])
        edges.update(observed[1])
        checked += 1
    wanted_positions = set(graph["played"]["positions"]) | set(graph["alternative"]["positions"])
    wanted_edges = set(graph["played"]["edges"]) | set(graph["alternative"]["edges"])
    incomplete = skipped > 0 or any(flags.values())
    covered_positions = len(wanted_positions & positions)
    covered_edges = len(wanted_edges & edges)
    return {
        "status": "incomplete" if incomplete else "checked",
        "checked_games": checked,
        "skipped_games": skipped,
        "covered_positions": covered_positions,
        "covered_edges": covered_edges,
        "not_seen_positions": None if incomplete else len(wanted_positions) - covered_positions,
        "not_seen_edges": None if incomplete else len(wanted_edges) - covered_edges,
        "time_projection": TIME_VERSION,
        "limits": {
            "games": MAX_GAMES,
            "positions_per_game": MAX_POSITIONS,
            "pgn_bytes": MAX_GAME_BYTES,
            "history_steps": HISTORY_LIMIT,
        },
        "uncertainty": flags,
    }
