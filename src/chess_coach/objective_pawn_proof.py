"""Reuse verified local WDL proof after an accepted promotion transition."""

import chess

from . import pawn_proof
from .pawn_proof_report import report
from .pawn_scope import history_known
from .pawn_scope import supported as pawn_supported


def supported(board):
    if pawn_supported(board):
        return True
    return _promotion_descendant(board)


def _promotion_descendant(board):
    return (
        type(board) is chess.Board
        and board.is_valid()
        and not board.chess960
        and not board.castling_rights
        and board.occupied.bit_count() <= 4
        and history_known(board)
        and any(move.promotion for move in board.move_stack)
    )


def inspect(board, *, node_limit):
    if not 1 <= node_limit <= pawn_proof.MAX_NODES:
        raise ValueError("invalid proof limits")
    if pawn_supported(board):
        return pawn_proof.inspect_reused(board, node_limit=node_limit)
    if not _promotion_descendant(board):
        return {"status": "unsupported", "reason": "composition_or_history"}
    tablebase = pawn_proof.open_verified()
    if tablebase is None:
        return {"status": "unknown", "reason": "proof_resources_unavailable"}
    try:
        return report(board, tablebase, node_limit, pawn_proof.MAX_PLIES)
    finally:
        tablebase.close()
