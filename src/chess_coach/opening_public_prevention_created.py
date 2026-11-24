"""Prove a knight fork created by the public recorded action."""

import chess

from .fork_defense_safety import quiet_after, safe_material
from .fork_defense_scan import scan
from .opening_public_prevention_response import alternative


def created(board, recorded, before, clock, start, deadline, check, charge, max_alternatives):
    after = quiet_after(board, recorded)
    if after is None or not safe_material(after, check=check):
        return None, "unsupported"
    found = scan(after, check=check, on_proof=charge)
    if found is None or found["uncertain"]:
        return None, "unsupported"
    proofs = _created_proofs(after, before, found["proven"])
    if not proofs:
        return None, None
    choice, reason = alternative(
        board, recorded, clock, start, deadline, check, charge, max_alternatives
    )
    if choice is None:
        return None, reason
    move, response = choice
    return {
        "origin": "created_by_recorded_move",
        "recorded_response_status": "not_assessed",
        "fork": proofs[0],
        "alternative_uci": move.uci(),
        "alternative_san": board.san(move),
        "response": response,
    }, None


def _created_proofs(after, before, proven):
    result = []
    for text, proof in proven.items():
        move = chess.Move.from_uci(text)
        squares = [chess.parse_square(square) for square in proof["targets"]]
        if after.piece_type_at(move.from_square) == chess.KNIGHT and before.get(text) != squares:
            result.append(proof)
    return result


def knights(board, before):
    return {
        text: squares
        for text, squares in before.items()
        if board.piece_type_at(chess.Move.from_uci(text).from_square) == chess.KNIGHT
    }
