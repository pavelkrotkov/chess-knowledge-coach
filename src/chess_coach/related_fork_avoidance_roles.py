"""Compare the particular bad-move and defended-target roles."""

import chess

from .related_fork_prevention_roles import compatible, describe


def describe_choice(board, good, bad, after_bad, proof):
    result = describe(board, good, after_bad, proof)
    mover = board.piece_at(bad.from_square)
    if mover is None or mover.color != board.turn:
        raise ValueError("bad move unavailable")
    result["bad_mover"] = mover.piece_type
    result["bad_targets_self"] = chess.square_name(bad.to_square) in proof["targets"]
    return result


def same_roles(source, candidate):
    return (
        compatible(source, candidate)
        and source["bad_mover"] == candidate["bad_mover"]
        and source["bad_targets_self"] == candidate["bad_targets_self"]
    )
