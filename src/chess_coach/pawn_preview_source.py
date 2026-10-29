"""Reconstruct pawn preview lineage and verify local proof resources."""

from . import pawn_inspection, pawn_proof, pawn_tables
from .decision_history import decision_board
from .material_context import context_for_position
from .pawn_coach_current_inputs import preview_inputs
from .pawn_scope import history_known, supported


def resources_available():
    if (
        pawn_inspection.VERSION != pawn_proof.VERSION
        or pawn_inspection.MANIFEST_SHA256 != pawn_tables.MANIFEST_SHA256
    ):
        return False
    tablebase = pawn_proof.open_verified()
    if tablebase is None:
        return False
    tablebase.close()
    return True


def _position_board(db, evidence):
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (evidence["position_id"],)
    ).fetchone()
    if position is None:
        raise ValueError
    source, fingerprint = pawn_inspection._source(db, position, evidence["subject"])
    board = decision_board(db, position)
    color = "white" if board.turn else "black"
    if color != source["color"] or not supported(board) or not history_known(board):
        raise ValueError
    board.parse_uci(position["uci"])
    return position, board, fingerprint


def recorded_source(db, evidence):
    position, board, fingerprint = _position_board(db, evidence)
    context = context_for_position(db, position["game_id"], position["id"], evidence["subject"])
    fact = evidence["facts"][0]["payload"]
    inputs = preview_inputs(db, evidence["facts"][0], fingerprint)
    if not pawn_inspection._still_current(db, position, evidence["subject"], fingerprint):
        raise ValueError
    return {
        "inputs": inputs,
        "context": context,
        "fact": fact,
        "report": {
            "game_id": position["game_id"],
            "ply": position["ply"],
            "decision_fen": board.fen(),
            "source_fingerprint": fingerprint,
            "played_uci": position["uci"],
        },
    }
