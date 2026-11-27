"""Validate bounded signed cursor values."""


def integer(value, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def text(value, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum


def hex_digest(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def common(common):
    if not hex_digest(common["binding"]):
        raise ValueError("invalid common continuation")
    if not integer(common["matches"], 0, 7):
        raise ValueError("invalid common continuation")
    if type(common["complete"]) is not bool or common["winner"] not in {None, "capture", "fork"}:
        raise ValueError("invalid common continuation")
    if common["winner"] is not None and not common["complete"]:
        raise ValueError("invalid common continuation")
