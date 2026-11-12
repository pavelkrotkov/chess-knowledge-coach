"""Run one restricted search and validate its measured work."""

import chess.engine

from .opening_decision_line_safety import MAX_PLIES
from .opening_experiment_line import MIN_PLIES
from .opening_measure_grade import selected
from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .purpose_deadline import search_timeout
from .purpose_iteration_search import search as retained_search
from .purpose_lines import work


def search(engine, board, position, alternative, deadline):
    timeout = search_timeout(deadline, FINAL_SECONDS)
    if timeout is None:
        return {"status": "insufficient", "reason": "deadline"}
    engine.timeout = timeout
    requested = [position["uci"], alternative]
    moves = [board.parse_uci(move) for move in requested]
    state, error = retained_search(
        engine,
        board,
        position,
        chess.engine.Limit(nodes=FINAL_NODES, time=FINAL_SECONDS),
        moves,
        deadline,
        bounds=(1, MAX_PLIES, MIN_PLIES),
    )
    if error:
        return {"status": "insufficient", "reason": error}
    activity = work([state.work], FINAL_NODES)
    if activity["nodes"] is None or activity["node_limit_exceeded"]:
        return {"status": "insufficient", "reason": "node_limit_unverified"}
    lines, reason = selected(board, position, requested, state.best)
    if reason:
        return {"status": "insufficient", "reason": reason}
    return {"status": "complete", "lines": lines, "work": activity, "retained_depth": state.depth}
