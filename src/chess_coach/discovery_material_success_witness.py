"""Prove a nominated material discovery from a distinct legal witness."""

import chess

from .discovery_geometry import discoveries
from .discovery_proof import prove
from .fork_defense_safety import quiet_after

MAX_MOVES = 64


def witness(board, played, candidates, check):
    moves = list(board.legal_moves)
    if len(moves) > MAX_MOVES:
        return None, "witness_move_limit"
    for move in sorted(moves, key=lambda item: item.uci()):
        check()
        found = _move(board, played, move, candidates, check)
        if found:
            return found, None
    return None, "witness_unavailable"


def _move(board, played, move, candidates, check):
    if move == played or move.promotion or board.is_castling(move):
        return None
    after = quiet_after(board, move)
    if after is None or after.ep_square is not None:
        return None
    for candidate in candidates:
        proof = _proof(board, after, move, candidate, check)
        if proof:
            return {
                "move": move.uci(),
                "san": board.san(move),
                "proof": proof,
                "target_origin": chess.square_name(candidate["target"]),
            }
    return None


# Follow the original target through the witness before proving any branch.
def _proof(board, after, move, candidate, check):
    origin = candidate["target"]
    target = move.to_square if move.from_square == origin else origin
    if after.piece_at(target) != board.piece_at(origin):
        return None
    try:
        attack = after.parse_uci(candidate["move"])
    except ValueError:
        return None
    if not _named(after, attack, candidate["slider"], target):
        return None
    return next(
        (
            proof
            for proof in prove(after, attack, check=check)
            if _matches(proof, candidate, target)
        ),
        None,
    )


def _named(board, attack, slider, target):
    return any(
        item["slider"] == slider and item["target"] == target for item in discoveries(board, attack)
    )


def _matches(proof, candidate, target):
    return (
        not proof["mate"]
        and proof["slider"] == chess.square_name(candidate["slider"])
        and proof["target"] == chess.square_name(target)
    )
