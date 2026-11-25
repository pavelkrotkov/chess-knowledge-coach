"""Read one current same-side public fork witness."""

import time

import chess

from .opening_fork_nomination_coverage import coverage
from .opening_fork_nomination_provenance import certificate
from .opening_public_proof_read import lookup


def _witness(proof, color, alternative):
    if proof is None:
        return None
    played = proof.get("branches", {}).get("played", {})
    forks = played.get("forks", {})
    example = forks.get("example")
    if not example or example.get("kind") != "material":
        return None
    board = chess.Board(example["fen"])
    if ("white" if board.turn else "black") != color or not certificate(example, board):
        return None
    return {
        "example": example,
        **coverage(proof, played, forks),
        "coverage": forks,
        "reference": proof["reference"],
        "version": proof["version"],
        "policy": proof["fork_policy"],
        "alternative": alternative,
        "window": proof["fork_window"],
    }


def source(db, root, learner, branch, alternatives, budget):
    exemplar = branch["exemplar"]
    for window in ("initial", "continuation"):
        for item in alternatives:
            if time.monotonic() >= budget.expires:
                return None
            alternative = item["uci"]
            proof = lookup(
                db,
                root,
                learner,
                exemplar["game_id"],
                exemplar["position_id"],
                alternative,
                budget.expires,
                fork_window=window,
            )
            witness = _witness(proof, branch["color"], alternative)
            if witness:
                return witness
    return None
