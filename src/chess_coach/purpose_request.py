"""Create an idempotent owned request without touching ordinary deep state."""

from .fact_fingerprint import canonical, digest
from .purpose_config import EARLY_CENTER, PURPOSE, VERSION, configuration
from .purpose_source import source


def fingerprint(snapshot, config):
    return digest(
        canonical(
            {
                "purpose": PURPOSE,
                "policy": config.get("purpose_policy", VERSION),
                "learner": snapshot["learner_key"],
                "game": snapshot["game_id"],
                "position": snapshot["position"]["id"],
                "source": snapshot["fingerprint"],
                "config": config,
            }
        )
    )


def create(db, position_id, learner, *, engine_path="/usr/games/stockfish", policy=VERSION):
    if type(position_id) is not int or position_id < 1:
        raise ValueError("invalid decision identifier")
    if db.connection.in_transaction:
        raise RuntimeError("purpose request requires an idle database")
    snapshot = source(db, position_id, learner)
    config = configured(db, snapshot, engine_path, policy)
    key = fingerprint(snapshot, config)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        fresh = source(db, position_id, learner)
        if fingerprint(fresh, config) != key:
            raise ValueError("source changed while creating request")
        db.connection.execute(
            """INSERT OR IGNORE INTO purpose_analysis_requests
            (game_id,position_id,learner_key,purpose,policy_version,
             source_fingerprint,config_json,request_fingerprint,status)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                snapshot["game_id"],
                position_id,
                snapshot["learner_key"],
                PURPOSE,
                policy,
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


def configured(db, snapshot, engine_path, policy):
    if policy == EARLY_CENTER:
        from .purpose_early_center import roots

        if not roots(snapshot["board"], snapshot["position"]):
            raise ValueError("early-center contrast unavailable")
        return configuration(db, snapshot["game_id"], engine_path, policy=policy)[1]
    if policy != VERSION:
        raise ValueError("unknown purpose policy")
    return configuration(db, snapshot["game_id"], engine_path)[1]
