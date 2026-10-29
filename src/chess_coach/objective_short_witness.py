"""Validate a stored proof and select a legal defensive continuation."""

from .mate_practice_defenses import defense_lines
from .mate_proof import VERSION as PROOF_VERSION
from .objective_short_history import history_hash, validate_later_events


def resume(db, session, row, result, board, move):
    proof = result["proof"]
    if proof["status"] != "proved" or proof["move"]["uci"] != move.uci():
        raise ValueError("continuation proof unavailable")
    board.push(move)
    if proof["distance_plies"] == 1 and board.is_checkmate():
        return {"board": board, "complete": True}
    lines = defense_lines(board, proof, move)
    selected = min(line.split() for line in lines)
    defense, mate = selected[1:]
    board.push(board.parse_uci(defense))
    validate_later_events(db, session, row["event_id"], board)
    return {"board": board, "defense": defense, "mate": mate, "complete": False}


def binding(row, result, board):
    fields = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "event_prefix_hash",
        "source_hash",
    )
    if any(result.get(field) != row[field] for field in fields):
        raise ValueError("continuation proof binding changed")
    if result.get("proof_version") != PROOF_VERSION:
        raise ValueError("continuation proof version changed")
    if result.get("verifier") != "mate-two-verifier-v1" or result.get(
        "history_hash"
    ) != history_hash(board):
        raise ValueError("continuation history changed")
