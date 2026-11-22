"""Certify one bounded public fork root or report unresolved geometry."""

import time

import chess

from .fork_proof import fork_proof
from .fork_targets import targets, unsupported_shape
from .opening_public_fork_example import example as bind_example
from .opening_public_fork_scope import supported
from .opening_public_proof_versions import PROOFS_PER_BRANCH


def _check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("public fork deadline")


def inspect(board, move, recorded, rows, ply, budget, deadline):
    _check(deadline)
    if not supported(board):
        return "scope", None
    shape = targets(board, move)
    if shape is None:
        return ("unsupported", None) if unsupported_shape(board, move) else ("none", None)
    after, squares = shape
    if after.is_checkmate():
        proof = {"targets": [chess.square_name(square) for square in squares], "distance_plies": 1}
        return "mate", bind_example(board, move, recorded, rows, ply, proof, "immediate_mate")
    if budget["proofs"] >= PROOFS_PER_BRANCH:
        return "limit", None
    budget["proofs"] += 1
    proof = fork_proof(board, move, check=lambda: _check(deadline))
    if proof is None:
        return "unsupported", None
    return "material", bind_example(board, move, recorded, rows, ply, proof, "material")
