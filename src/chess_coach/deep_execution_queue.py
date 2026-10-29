"""Create and recover owned jobs without changing selection history."""

from .deep_execution_selection import current_selection
from .fact_fingerprint import canonical, digest
from .mapping_transaction import mapping_transaction


def prepare_jobs(db, selection_id, learner, config, retry_insufficient):
    fingerprint = digest(canonical(config))
    with mapping_transaction(db):
        selection = current_selection(db, selection_id, learner)
        for item in selection["items"]:
            job_id = _job(
                db, selection_id, item["position_id"], fingerprint, config, retry_insufficient
            )
            db.connection.execute(
                """INSERT INTO deep_analysis_current(selection_id,position_id,job_id) VALUES(?,?,?)
                ON CONFLICT(selection_id,position_id) DO UPDATE SET job_id=excluded.job_id""",
                (selection_id, item["position_id"], job_id),
            )
    return selection


def recover_jobs(db):
    with mapping_transaction(db):
        _recover(db)


def _recover(db):
    db.connection.execute(
        """UPDATE deep_analysis_attempts SET status='interrupted',detail='worker_interrupted',
        finished_at=CURRENT_TIMESTAMP WHERE status='running'"""
    )
    db.connection.execute(
        "UPDATE deep_analysis_jobs SET status='pending',updated_at=CURRENT_TIMESTAMP WHERE status='running'"
    )


def _job(db, selection_id, position_id, fingerprint, config, retry_insufficient):
    db.connection.execute(
        """INSERT OR IGNORE INTO deep_analysis_jobs
        (selection_id,position_id,config_fingerprint,config_json,status) VALUES(?,?,?,?,'pending')""",
        (selection_id, position_id, fingerprint, canonical(config)),
    )
    row = db.connection.execute(
        "SELECT id,status,config_json FROM deep_analysis_jobs WHERE selection_id=? AND position_id=? AND config_fingerprint=?",
        (selection_id, position_id, fingerprint),
    ).fetchone()
    if row is None or row["config_json"] != canonical(config):
        raise ValueError("deep job configuration conflicts")
    if row["status"] == "stale" or (retry_insufficient and row["status"] == "insufficient"):
        db.connection.execute(
            "UPDATE deep_analysis_jobs SET status='pending',updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (row["id"],),
        )
    return row["id"]


def pending_jobs(db, selection_id, limit):
    return db.connection.execute(
        """SELECT j.* FROM deep_analysis_jobs j JOIN deep_analysis_current c ON c.job_id=j.id
        JOIN deep_selection_items i ON i.selection_id=j.selection_id AND i.position_id=j.position_id
        WHERE j.selection_id=? AND j.status='pending' ORDER BY i.rank LIMIT ?""",
        (selection_id, limit),
    ).fetchall()
