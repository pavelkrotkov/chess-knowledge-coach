"""Persist sanitized run and synchronization health across restarts."""

from datetime import UTC, datetime

from .db import Database
from .mapping_transaction import mapping_transaction


def _now() -> str:
    return datetime.now(UTC).isoformat()


def start_run(db: Database) -> None:
    with mapping_transaction(db):
        db.connection.execute(
            """INSERT INTO pipeline_health(id,status,started_at,sync_status)
            VALUES (1,"running",?,"pending") ON CONFLICT(id) DO UPDATE SET
            status="running",started_at=excluded.started_at,finished_at=NULL,
            sync_status="pending",sync_detail=NULL,sync_at=NULL""",
            (_now(),),
        )


def record_sync(db: Database, result: dict) -> None:
    now = _now()
    success = result["status"] in {"complete", "partial"} and "detail" not in result
    with mapping_transaction(db):
        db.connection.execute(
            """UPDATE pipeline_health SET sync_status=?,sync_detail=?,sync_at=?,
            last_sync_success_at=CASE WHEN ? THEN ? ELSE last_sync_success_at END WHERE id=1""",
            (result["status"], result.get("detail"), now, success, now),
        )


def finish_run(db: Database, status: str) -> None:
    now = _now()
    with mapping_transaction(db):
        db.connection.execute(
            """UPDATE pipeline_health SET status=?,finished_at=?,
            last_success_at=CASE WHEN ? THEN ? ELSE last_success_at END WHERE id=1""",
            (status, now, status == "complete", now),
        )


def run_status(db: Database, sync: dict, games: list, scan: dict) -> str:
    if sync["status"] == "failed":
        return "failed"
    pending = db.connection.execute(
        'SELECT 1 FROM pipeline_stages WHERE status != "complete" LIMIT 1'
    ).fetchone()
    if sync["status"] != "complete" or scan["has_more"] or pending is not None:
        return "partial"
    return "partial" if any(game["status"] != "complete" for game in games) else "complete"
