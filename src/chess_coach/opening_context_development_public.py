"""Qualify current source-bound material forks without running a proof."""

import chess

from .opening_fork_nomination_provenance import certificate


def _example(prepared):
    if prepared["status"] != "prepared" or prepared["coverage"]["status"] != "checked":
        return None
    example = prepared["coverage"]["result"]["example"]
    return example if example and example["kind"] == "material" else None


def witness(item, color):
    prepared = item["public_fork"]
    example = _example(prepared)
    if example is None:
        return None
    coverage = prepared["coverage"]
    board = chess.Board(example["fen"])
    if ("white" if board.turn else "black") != color or not certificate(example, board):
        return None
    if example["ply"] <= prepared["binding"]["source"]["history"]["ply"]:
        return None
    return {
        "binding_sha256": prepared["binding_sha256"],
        "example": example,
        "coverage": coverage,
        "source": prepared["binding"]["source"],
        "policy": prepared["binding"]["policy"],
    }
