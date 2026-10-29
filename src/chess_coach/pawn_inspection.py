"""Read-only pawn proof for a current, learner-owned decision."""

from .decision_history import decision_board
from .deep_selection_source import source_snapshot
from .fact_fingerprint import canonical, digest
from .pawn_proof import VERSION
from .pawn_proof import inspect_reused as inspect
from .pawn_tables import MANIFEST_SHA256


def _source(db, position, learner):
    source = source_snapshot(db, position["game_id"], learner)
    fingerprint = digest(
        canonical(
            {
                "version": VERSION,
                "proof_manifest_sha256": MANIFEST_SHA256,
                "source": source["input_fingerprint"],
                "run_id": source["cheap_run_id"],
                "position": position["id"],
                "ply": position["ply"],
                "played": position["uci"],
            }
        )
    )
    return source, fingerprint


def _still_current(db, position, learner, fingerprint):
    try:
        return _source(db, position, learner)[1] == fingerprint
    except ValueError:
        return False


def inspect_pawn(db, position_id, *, learner, expected_fingerprint=None):
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError("decision unavailable")
    try:
        source, fingerprint = _source(db, position, learner)
        board = decision_board(db, position)
        if ("white" if board.turn else "black") != source["color"]:
            raise ValueError("not the learner decision")
        if expected_fingerprint is not None and expected_fingerprint != fingerprint:
            return {"status": "stale", "version": VERSION}
        proof = inspect(board)
    except ValueError:
        return {"status": "unavailable", "version": VERSION}
    if not _still_current(db, position, learner, fingerprint):
        return {"status": "stale", "version": VERSION}
    return {
        "status": "current",
        "version": VERSION,
        "proof_manifest_sha256": MANIFEST_SHA256,
        "source_fingerprint": fingerprint,
        "analysis_run_id": source["cheap_run_id"],
        "game_id": position["game_id"],
        "position_id": position_id,
        "ply": position["ply"],
        "decision_fen": board.fen(),
        "learner_color": source["color"],
        "played": board.san(board.parse_uci(position["uci"])),
        "proof": proof,
    }
