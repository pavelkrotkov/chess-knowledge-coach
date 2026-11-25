"""Validate retained new and due prompt identities."""


def _keys(keys, seen):
    if not isinstance(keys, list) or len(keys) > 50 or len(keys) != len(set(keys)):
        raise ValueError("invalid practice window history")
    if any(not isinstance(key, str) or key not in seen for key in keys):
        raise ValueError("invalid practice window history")


def validate_history(value):
    if type(value["source_refreshed"]) is not bool:
        raise ValueError("invalid practice window refresh")
    seen = value["state"].get("seen", [])
    for field in ("new_seen", "repeat_due"):
        _keys(value[field], seen)
    if not set(value["repeat_due"]).issubset(value["new_seen"]):
        raise ValueError("invalid practice window history")
