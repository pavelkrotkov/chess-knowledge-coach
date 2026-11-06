"""Present terminal direct-public deviations without inventing a verifier."""

import json

import chess

from .objective_promotion_contract import OBJECTIVES


def direct(row):
    if row["source_type"] != "public":
        return False
    provenance = json.loads(row["provenance_json"])
    return not any(key.startswith("related_") for key in provenance)


def outcome(row):
    if row["status"] != "needs_verification" or row["objective"] in OBJECTIVES:
        return None
    if row["source_type"] != "public":
        return None
    if direct(row) and row["objective"] == "checkmate" and _mate(row["current_fen"]):
        return "checkmate_reached"
    return "ungraded"


def _mate(fen):
    try:
        board = chess.Board(fen)
        return board.is_valid() and board.is_checkmate()
    except ValueError:
        return False
