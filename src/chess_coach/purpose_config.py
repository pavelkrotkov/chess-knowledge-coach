"""Fixed limits and policy for one explicit candidate-set diagnostic."""

from .deep_execution_config import DeepOptions, prepare_config

PURPOSE = "candidate-comparison"
VERSION = "candidate-comparison-v1"
EARLY_CENTER = "candidate-comparison-early-center-v1"
SCOUT_NODES = 50000
SCOUT_SECONDS = 0.5
FINAL_NODES = 200000
FINAL_SECONDS = 1.5
MAX_ATTEMPTS = 2
WORKER_SECONDS = 25.0


def configuration(db, game_id, engine_path, *, policy=VERSION):
    options = DeepOptions(
        engine_path=engine_path,
        nodes=FINAL_NODES,
        seconds=FINAL_SECONDS,
        multipv=2,
        threads=1,
        hash_mb=16,
        min_depth=4,
        max_jobs=1,
    )
    binary, _, config = prepare_config(db, game_id, options, allow_transaction=True)
    config.update(
        {
            "purpose": PURPOSE,
            "purpose_policy": policy,
            "scout_nodes": SCOUT_NODES,
            "scout_seconds": SCOUT_SECONDS,
            "candidate_set": "played-and-scout-nominee",
            "worker_seconds": WORKER_SECONDS,
        }
    )
    if policy == EARLY_CENTER:
        config["scout_root_policy"] = "opposite-central-pawn-capture-v1"
    elif policy != VERSION:
        raise ValueError("unknown purpose policy")
    return binary, config
