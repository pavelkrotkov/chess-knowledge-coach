"""Check completeness of a retained fork certificate without a solver."""

import chess

from .unified_fork_bounds import _branches


def _capture(after, branch, attacker, targets):
    replay = after.copy()
    replay.push_uci(branch["reply"])
    move = replay.parse_uci(branch["capture"])
    return replay.is_capture(move) and move.from_square == attacker and move.to_square in targets


def _replies_match(after, branches):
    return {branch["reply"] for branch in branches} == {move.uci() for move in after.legal_moves}


def certificate(example, board):
    proof = example.get("proof")
    if not isinstance(proof, dict):
        return False
    detail = {"move": example.get("candidate_uci"), "proof": proof}
    try:
        if not _branches(detail, example.get("anchor")):
            return False
        after = board.copy()
        after.push_uci(example["candidate_uci"])
        if not _replies_match(after, proof["branches"]):
            return False
        attacker = chess.parse_square(proof["attacker"])
        targets = {chess.parse_square(name) for name in proof["targets"]}
        return all(_capture(after, branch, attacker, targets) for branch in proof["branches"])
    except (KeyError, TypeError, ValueError):
        return False
