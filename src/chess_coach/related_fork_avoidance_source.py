"""Reconstruct a current source whose bad move created a particular fork."""

import chess

from .decision_history import decision_board
from .fork_defense_probe import hypothetical
from .fork_defense_safety import quiet_after
from .mate_inspection_source import position_row
from .related_fork_avoidance_snapshot import result
from .related_fork_prevention_source_current import current


def source_for_evidence(db, subject, evidence_id):
    try:
        return _load(db, subject, evidence_id)
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ValueError("fork avoidance source unavailable or stale") from None


def _load(db, subject, evidence_id):
    evidence = current(db, subject, evidence_id)
    fact = evidence["facts"][0]
    payload = fact["payload"]
    if payload["outcome"] != "failure" or payload.get("threat_origin") != "created_by_played_move":
        raise ValueError("not a created-by-play fork source")
    board = decision_board(db, position_row(db, evidence["position_id"]))
    good = board.parse_uci(payload["best"]["uci"][0])
    bad = board.parse_uci(payload["played"]["uci"][0])
    after_bad = quiet_after(board, bad)
    before = hypothetical(board)
    proof = payload["fork"]
    if good not in board.legal_moves or after_bad is None or before is None:
        raise ValueError("created fork witness unavailable")
    if before.get(proof["move"]) == [chess.parse_square(s) for s in proof["targets"]]:
        raise ValueError("fork existed before the played move")
    return result(db, evidence, fact, board, good, bad, after_bad, proof)
