"""Atomically retain the latest requested retry deadline."""

from .db import Database
from .mapping_transaction import mapping_transaction


def persist_deadline(db: Database, now: str, deadline: str) -> None:
    with mapping_transaction(db):
        db.connection.execute(
            """INSERT INTO pipeline_health
            (id,status,started_at,sync_status,sync_detail,sync_at,retry_until)
            VALUES (1,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            sync_status=excluded.sync_status,sync_detail=excluded.sync_detail,
            sync_at=excluded.sync_at,retry_until = CASE
            WHEN pipeline_health.retry_until IS NULL OR pipeline_health.retry_until < excluded.retry_until
            THEN excluded.retry_until ELSE pipeline_health.retry_until END""",
            ("running", now, "waiting", "server_backoff", now, deadline),
        )
