"""Check exact legacy mate facts against legal outcomes."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .tactical_rules import mate_in_one_fact


def legacy_fact(fact, outcome):
    if not _legacy_source(fact):
        return False
    payload = fact["payload"]
    try:
        verified = mate_in_one_fact(payload["pre_move_fen"], payload["played_move"])
    except (KeyError, ValueError, TypeError):
        return False
    return verified == payload and _legacy_outcome(payload, outcome)


def _legacy_source(fact):
    return (
        fact["producer"] == "mate-in-one"
        and fact["fact_type"] == "mate_in_one"
        and fact["detector_version"] == fact["run_detector_version"] == "1.0.0"
        and fact["detector_status"] == "active"
        and isinstance(fact["payload"], dict)
    )


def _legacy_outcome(payload, outcome):
    return (outcome == "success" and payload["played_checkmate"]) or (
        outcome == "failure" and payload["played_stalemate"]
    )


def matches_game(db, row, fact):
    try:
        position = position_row(db, row["position_id"])
        board = decision_board(db, position)
        payload = fact["payload"]
        return payload["pre_move_fen"] == board.fen() and payload["played_move"] == position["uci"]
    except (ValueError, TypeError, KeyError):
        return False
