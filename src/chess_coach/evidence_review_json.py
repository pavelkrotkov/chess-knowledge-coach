"""Preserve legacy JSON values even when historical data is malformed."""

import json


def decode(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def decision_fen(context):
    return context.get("pre_move_fen") if isinstance(context, dict) else None


def legacy_validation(value):
    if not value:
        return None
    return {"accepted": True, "actor": None, "reviewed_at": None}
