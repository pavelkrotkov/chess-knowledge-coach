"""Read the optional scheduled-item identity for unified practice."""

from flask import request


def item_id():
    value = request.form.get("item_id")
    if value is None:
        return None
    if not value.isascii() or not value.isdigit() or not 0 < int(value) < 2**63:
        raise ValueError("invalid training item")
    return int(value)
