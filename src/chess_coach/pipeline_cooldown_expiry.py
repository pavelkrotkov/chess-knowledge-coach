"""Consume only a retry deadline whose bounded attempt has finished."""

from .mapping_transaction import mapping_transaction
from .pipeline_cooldown import active_deadline, stored_deadline


def clear_expired(db, clock, previous, result):
    deadline = stored_deadline(db)
    if result.get("detail") == "worker_process_required":
        return
    if deadline is None or active_deadline(db, clock) is not None:
        return
    if deadline != previous and result["status"] not in {"complete", "partial"}:
        return
    with mapping_transaction(db):
        db.connection.execute(
            "UPDATE pipeline_health SET retry_until=NULL WHERE id=1 AND retry_until=?", (deadline,)
        )
