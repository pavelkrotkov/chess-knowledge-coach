"""Store immutable structure episode generations."""

from datetime import UTC, datetime

from .db import Database
from .fact_fingerprint import canonical, digest
from .structure_features import _structure_names


def persist_episodes(
    db: Database,
    game_id: int,
    version: str,
    rows,
    episodes: list,
    pipeline_generation: int | None = None,
) -> int:
    input_hash = digest(canonical([list(row) for row in rows]))
    if pipeline_generation is not None:
        input_hash = digest(
            canonical({"base": input_hash, "pipeline_generation": pipeline_generation})
        )
    output_hash = digest(canonical(episodes))
    old = db.connection.execute(
        """SELECT * FROM structure_runs WHERE game_id = ? AND detector_version = ?
        AND input_hash = ?""",
        (game_id, version, input_hash),
    ).fetchone()
    if old is not None:
        if old["output_hash"] != output_hash:
            raise ValueError("structure output changed for the same input and detector version")
        return len(episodes)
    run_id, now = _append_run(db, game_id, version, input_hash, output_hash, pipeline_generation)
    for start, end, features in episodes:
        db.connection.execute(
            """INSERT INTO structure_episodes
            (game_id, start_ply, end_ply, features_json, structure_json, confidence,
             detector_version, run_id, produced_at) VALUES (?, ?, ?, ?, ?, 1.0, ?, ?, ?)""",
            (
                game_id,
                start,
                end,
                canonical(features),
                canonical(_structure_names(features)),
                version,
                run_id,
                now,
            ),
        )
    return len(episodes)


def _append_run(
    db: Database,
    game_id: int,
    version: str,
    input_hash: str,
    output_hash: str,
    pipeline_generation: int | None,
) -> tuple[int, str]:
    old = db.connection.execute(
        "SELECT id FROM structure_runs WHERE game_id = ? AND status = 'active'", (game_id,)
    ).fetchone()
    if old is not None:
        db.connection.execute(
            "UPDATE structure_runs SET status = 'superseded' WHERE id = ?", (old["id"],)
        )
    now = datetime.now(UTC).isoformat()
    cursor = db.connection.execute(
        """INSERT INTO structure_runs(game_id, detector_version, input_hash, output_hash,
        produced_at, status, supersedes_run_id, pipeline_generation) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
        (
            game_id,
            version,
            input_hash,
            output_hash,
            now,
            old["id"] if old else None,
            pipeline_generation,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a structure run ID")
    return cursor.lastrowid, now
