"""Verify an existing immutable selection matches deterministic replay."""

import json


def verify_replay(db, existing, config, coverage, selected):
    stored = db.connection.execute(
        "SELECT position_id,rank,allocation,reasons_json FROM deep_selection_items WHERE selection_id=? ORDER BY rank",
        (existing["id"],),
    ).fetchall()
    actual = [
        (row["position_id"], row["rank"], row["allocation"], json.loads(row["reasons_json"]))
        for row in stored
    ]
    expected = [
        (item["position_id"], rank, item["allocation"], item["reasons"])
        for rank, item in enumerate(selected, 1)
    ]
    if (
        json.loads(existing["config_json"]) != config
        or json.loads(existing["coverage_json"]) != coverage
        or actual != expected
    ):
        raise ValueError("stored selection differs from deterministic replay")
