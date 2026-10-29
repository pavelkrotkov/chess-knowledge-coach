"""Owned current-analysis lineage for on-demand mate inspection."""

from .decision_history import decision_board
from .deep_selection_source import source_snapshot
from .fact_fingerprint import canonical, digest
from .mate_proof import VERSION


def position_row(db, position_id):
    row = db.connection.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if row is None:
        raise ValueError("decision is unavailable")
    return row


def _fingerprint(snapshot, position):
    return digest(
        canonical(
            {
                "version": VERSION,
                "source": snapshot["input_fingerprint"],
                "run_id": snapshot["cheap_run_id"],
                "position": position["id"],
                "ply": position["ply"],
                "played": position["uci"],
            }
        )
    )


def source(db, position, learner):
    snapshot = source_snapshot(db, position["game_id"], learner)
    return snapshot, _fingerprint(snapshot, position)


def checked_board(db, position, snapshot):
    board = decision_board(db, position)
    color = "white" if board.turn else "black"
    if color != snapshot["color"] or not board.is_valid() or board.outcome(claim_draw=False):
        raise ValueError("decision is unavailable")
    return board


def still_current(db, position, learner, fingerprint):
    try:
        _, after = source(db, position, learner)
    except ValueError:
        return False
    return after == fingerprint
