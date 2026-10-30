"""Build purpose source snapshots from already reconstructed report boards."""

from .purpose_source_batch import snapshots


def sources(db, game_id, learner, rows, boards):
    ids = {row["position_id"] for row in rows}
    selected = {key: boards[key] for key in ids if key in boards}
    try:
        return snapshots(db, game_id, learner, ids, boards=selected)
    except (ValueError, TypeError, IndexError):
        return {}
