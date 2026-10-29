"""Validate own-game evidence keys before SQLite lookup."""


def evidence_id(key):
    if not isinstance(key, str) or not key.isascii() or not key.isdecimal() or key.startswith("0"):
        raise ValueError("practice source unavailable")
    if len(key) > 19 or int(key) > 9223372036854775807:
        raise ValueError("practice source unavailable")
    return int(key)
