"""Store immutable opening classifications, including no-match results."""

from datetime import UTC, datetime

from .classification_inputs import opening_input
from .db import Database
from .fact_fingerprint import canonical, digest


def persist_opening(db: Database, game_id: int, dataset_id: int, version: str, best) -> dict:
    input_hash = opening_input(db, game_id, dataset_id)
    result = (
        {"matched": False, "confidence": 0.0}
        if best is None
        else {"matched": True, "eco": best["eco"], "name": best["name"], "confidence": 1.0}
    )
    output_hash = digest(canonical({"result": result, "node_id": best["id"] if best else None}))
    prior = db.connection.execute(
        """SELECT * FROM opening_runs WHERE game_id = ? AND dataset_id = ?
        AND classifier_version = ? AND input_hash = ?""",
        (game_id, dataset_id, version, input_hash),
    ).fetchone()
    if prior is not None:
        if prior["output_hash"] != output_hash:
            raise ValueError("opening output changed for the same input and classifier version")
        return result
    run_id, now = _append_run(db, game_id, dataset_id, version, input_hash, output_hash)
    db.connection.execute(
        """INSERT INTO game_openings(game_id, dataset_id, opening_node_id, confidence, run_id, produced_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (game_id, dataset_id, best["id"] if best else None, result["confidence"], run_id, now),
    )
    return result


def _append_run(
    db: Database, game_id: int, dataset_id: int, version: str, input_hash: str, output_hash: str
) -> tuple[int, str]:
    old = db.connection.execute(
        "SELECT id FROM opening_runs WHERE game_id = ? AND status = 'active'", (game_id,)
    ).fetchone()
    if old is not None:
        db.connection.execute(
            "UPDATE opening_runs SET status = 'superseded' WHERE id = ?", (old["id"],)
        )
    now = datetime.now(UTC).isoformat()
    cursor = db.connection.execute(
        """INSERT INTO opening_runs(game_id, dataset_id, classifier_version, input_hash, output_hash,
        produced_at, status, supersedes_run_id) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
        (game_id, dataset_id, version, input_hash, output_hash, now, old["id"] if old else None),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return an opening run ID")
    return cursor.lastrowid, now
