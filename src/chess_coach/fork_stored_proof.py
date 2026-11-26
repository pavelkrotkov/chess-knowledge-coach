"""Replay an unchanged versioned fork fact and its original detector output."""

from .fact_fingerprint import digest
from .fact_inputs import fact_batch
from .fact_storage import replay_result
from .fork_contract import PRODUCER, VERSION


def replay(db, prepared, fact):
    run = db.connection.execute(
        "SELECT * FROM detector_runs_read WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    if run is None or (
        run["producer"],
        run["detector_version"],
        run["status"],
        run["position_id"],
    ) != (PRODUCER, VERSION, "active", prepared["position_id"]):
        raise ValueError("fork detector run changed")
    if fact["fact_type"] != "fork_opportunity" or digest(run["input_json"]) != run["input_hash"]:
        raise ValueError("fork detector input changed")
    items, output_hash = fact_batch([{"fact_type": fact["fact_type"], "payload": fact["payload"]}])
    if replay_result(db.connection, run, output_hash, items)["fact_ids"] != [fact["id"]]:
        raise ValueError("fork detector fact changed")
    return fact["payload"]
