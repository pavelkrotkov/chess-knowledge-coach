"""Consume only a retry deadline whose bounded attempt has finished."""

from .mapping_transaction import mapping_transaction
from .mastery_time import parse_utc
from .pipeline_cooldown import stored_deadline, utc_now


def clear_expired(db, clock, previous, result):
    deadline = stored_deadline(db)
    if result.get("detail") == "worker_process_required":
        return
    if deadline is None or parse_utc(deadline) > utc_now(clock):
        return
    if deadline != previous and result["status"] not in {"complete", "partial"}:
        return
    with mapping_transaction(db):
        db.connection.execute(
            "UPDATE pipeline_health SET retry_until=NULL WHERE id=1 AND retry_until=?", (deadline,)
        )
