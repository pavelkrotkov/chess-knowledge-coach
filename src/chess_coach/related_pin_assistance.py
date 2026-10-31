"""Identify pin-transfer sessions for durable hint and reveal accounting."""

import json


def assistance(row):
    if row["source_type"] not in {"corpus", "public"}:
        return False
    return isinstance(json.loads(row["provenance_json"]).get("related_pin"), dict)
