"""Create an idempotent owned request without touching ordinary deep state."""

from .fact_fingerprint import canonical, digest
from .purpose_config import PURPOSE, VERSION, configuration
from .purpose_source import source


def fingerprint(snapshot, config):
    return digest(
        canonical(
            {
                "purpose": PURPOSE,
                "policy": VERSION,
                "learner": snapshot["learner_key"],
                "game": snapshot["game_id"],
                "position": snapshot["position"]["id"],
                "source": snapshot["fingerprint"],
                "cheap_run": snapshot["cheap_run_id"],
                "config": config,
            }
        )
    )


def create(db, position_id, learner, *, engine_path="/usr/games/stockfish"):
    if type(position_id) is not int or position_id < 1:
        raise ValueError("invalid decision identifier")
    if db.connection.in_transaction:
        raise RuntimeError("purpose request requires an idle database")
    snapshot = source(db, position_id, learner)
    _, config = configuration(db, snapshot["game_id"], engine_path)
    key = fingerprint(snapshot, config)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        fresh = source(db, position_id, learner)
        if fingerprint(fresh, config) != key:
            raise ValueError("source changed while creating request")
        db.connection.execute(
            """INSERT OR IGNORE INTO purpose_analysis_requests
            (game_id,position_id,learner_key,purpose,policy_version,cheap_run_id,
             source_fingerprint,config_json,request_fingerprint,status)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot["game_id"],
                position_id,
                snapshot["learner_key"],
                PURPOSE,
                VERSION,
                snapshot["cheap_run_id"],
                snapshot["fingerprint"],
                canonical(config),
                key,
                "pending",
            ),
        )
        row = db.connection.execute(
            "SELECT id,status FROM purpose_analysis_requests WHERE request_fingerprint=?", (key,)
        ).fetchone()
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
    return {"request_id": row["id"], "status": row["status"]}
