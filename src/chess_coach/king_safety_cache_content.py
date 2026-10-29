"""Check the stored fact batch against its immutable digest."""

import json

from .fact_inputs import fact_batch
from .king_safety_lesson import VERSION


def _valid_fact(fact, position_id):
    return (
        fact["position_id"] == position_id
        and fact["detector_version"] == VERSION
        and fact["fact_type"] == "king_safety_lesson"
    )


def _valid_batch(facts, batch, output, row, position_id):
    return (
        len(facts) <= 1
        and output == row["output_hash"]
        and all(_valid_fact(f, position_id) for f in facts)
        and sorted(f["fact_key"] for f in facts) == [item[0] for item in batch]
    )


def content(db, row, position_id):
    facts = db.connection.execute(
        "SELECT * FROM detector_facts WHERE run_id=?", (row["id"],)
    ).fetchall()
    items = [{"fact_type": f["fact_type"], "payload": json.loads(f["payload_json"])} for f in facts]
    batch, output = fact_batch(items)
    if not _valid_batch(facts, batch, output, row, position_id):
        return None
    return facts, items
