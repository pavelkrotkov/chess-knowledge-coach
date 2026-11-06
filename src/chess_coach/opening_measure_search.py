"""Run one restricted search and validate its measured work."""

import chess.engine

from .deep_execution_uci import analyse
from .opening_measure_grade import grade
from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .purpose_deadline import search_timeout
from .purpose_lines import work


def search(engine, board, position, alternative, deadline):
    timeout = search_timeout(deadline, FINAL_SECONDS)
    if timeout is None:
        return {"status": "insufficient", "reason": "deadline"}
    engine.timeout = timeout
    requested = [position["uci"], alternative]
    moves = [board.parse_uci(move) for move in requested]
    raw, error = analyse(
        engine, board, chess.engine.Limit(nodes=FINAL_NODES, time=FINAL_SECONDS), 2, moves
    )
    if error:
        return {"status": "insufficient", "reason": error}
    activity = work(raw, FINAL_NODES)
    if activity["nodes"] is None or activity["node_limit_exceeded"]:
        return {"status": "insufficient", "reason": "node_limit_unverified"}
    lines, reason = grade(board, position, requested, raw, error)
    if reason:
        return {"status": "insufficient", "reason": reason}
    return {"status": "complete", "lines": lines, "work": activity}
