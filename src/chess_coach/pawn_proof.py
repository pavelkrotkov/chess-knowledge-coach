"""Owned pawn-endgame analysis using verified local WDL and bounded legal search."""

from . import pawn_proof_cache, pawn_tables
from .pawn_geometry import describe
from .pawn_proof_report import report
from .pawn_scope import history_known, supported
from .pawn_tables import open_verified

VERSION = "pawn-proof-v2"
MAX_NODES = 6000
MAX_PLIES = 5


def inspect(board, *, node_limit=MAX_NODES, max_plies=MAX_PLIES):
    """Analyze legal alternatives from the original board without changing it."""
    return _inspect(board, node_limit, max_plies, reuse=False)


def inspect_reused(board, *, node_limit=MAX_NODES, max_plies=MAX_PLIES):
    """Reuse mathematical proof only after the local resources are freshly verified."""
    return _inspect(board, node_limit, max_plies, reuse=True)


def _inspect(board, node_limit, max_plies, *, reuse):
    if not 1 <= node_limit <= MAX_NODES or not 1 <= max_plies <= MAX_PLIES:
        raise ValueError("invalid proof limits")
    if not supported(board):
        return {"status": "unsupported", "reason": "composition_or_position"}
    if not history_known(board):
        return {"status": "unknown", "reason": "incomplete_repetition_history"}
    tablebase = open_verified()
    if tablebase is None:
        return {"status": "unknown", "reason": "proof_resources_unavailable"}
    try:
        return pawn_proof_cache.proof(
            board,
            tablebase,
            node_limit,
            max_plies,
            reuse,
            VERSION,
            pawn_tables.MANIFEST_SHA256,
            report,
            describe,
        )
    finally:
        tablebase.close()
