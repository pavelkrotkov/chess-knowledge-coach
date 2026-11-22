"""Run one restricted search and validate its measured work."""

import chess.engine

from .opening_decision_line_safety import MAX_PLIES
from .opening_experiment_line import MIN_PLIES
from .opening_measure_grade import selected
from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .purpose_deadline import search_timeout
from .purpose_iteration_search import search as retained_search
from .purpose_lines import work


def search(engine, board, position, alternative, deadline, *, reference=False):
    timeout = search_timeout(deadline, FINAL_SECONDS)
    if timeout is None:
        return {"status": "insufficient", "reason": "deadline"}
    engine.timeout = timeout
    requested, moves, nodes, seconds, options = _request(board, position, alternative, reference)
    state, error = retained_search(
        engine,
        board,
        position,
        chess.engine.Limit(nodes=nodes, time=seconds),
        moves,
        deadline,
        bounds=(1, MAX_PLIES, MIN_PLIES),
        **options,
    )
    if error:
        return {"status": "insufficient", "reason": error}
    activity = work([state.work], FINAL_NODES)
    if activity["nodes"] is None or activity["node_limit_exceeded"]:
        return {"status": "insufficient", "reason": "node_limit_unverified"}
    if reference:
        return _reference(state, activity, nodes)
    lines, reason = selected(board, position, requested, state.best)
    if reason:
        return {"status": "insufficient", "reason": reason}
    return {"status": "complete", "lines": lines, "work": activity, "retained_depth": state.depth}


def _request(board, position, alternative, reference):
    requested = [position["uci"], alternative]
    moves = list(board.legal_moves) if reference else [board.parse_uci(move) for move in requested]
    nodes, seconds = (180000, 1.35) if reference else (FINAL_NODES, FINAL_SECONDS)
    return requested, moves, nodes, seconds, {"reference": True} if reference else {}


def _reference(state, activity, requested_nodes):
    # Requested headroom does not replace checking the engine's actual time.
    seconds = activity.get("time_seconds")
    if state.invalid_work or seconds is None or seconds > FINAL_SECONDS:
        return {"status": "insufficient", "reason": "work_limit_unverified"}
    if not state.best:
        return {"status": "insufficient", "reason": "complete_iteration_unavailable"}
    activity["requested_nodes"] = requested_nodes
    return {
        "status": "complete",
        "policy": "all-legal-roots-v2",
        "lines": [{"rank": item["rank"], **item["line"]} for item in state.best],
        "work": activity,
        "retained_depth": state.depth,
    }
