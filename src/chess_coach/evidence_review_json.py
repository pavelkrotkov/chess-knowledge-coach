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
    if value == 0:
        return None
    if value == 1:
        return {"accepted": True, "actor": None, "reviewed_at": None}
    return {"accepted": None, "actor": None, "reviewed_at": None, "raw_flag": value}


def legacy_status(value):
    if value == 1:
        return "legacy_accepted"
    if value == 0:
        return "unreviewed"
    return "legacy_unknown"
