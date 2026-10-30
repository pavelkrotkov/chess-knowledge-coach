"""Reject unsupported pawn proof inputs before bounded evaluation."""

from . import pawn_proof, pawn_tables
from .objective_pawn_proof import supported
from .pawn_scope import history_known


def reason(board, move, data, clock, start, seconds):
    if clock() - start > seconds:
        return "timeout"
    if not supported(board) or not history_known(board):
        return "pawn_history_or_scope_unavailable"
    if board.is_game_over(claim_draw=True) or not move or move not in board.legal_moves:
        return "terminal_or_illegal_move"
    if not _proof_current(data):
        return "proof_version_changed"
    return None


def _proof_current(data):
    return (
        data.get("proof_version") == pawn_proof.VERSION
        and data.get("proof_manifest_sha256") == pawn_tables.MANIFEST_SHA256
    )
