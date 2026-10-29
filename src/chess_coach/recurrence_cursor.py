"""Bind evidence keyset pages to a learner, database, window and skill pair."""

import base64
import binascii
import json

from .fact_fingerprint import canonical

MAX_ID = 9223372036854775807


def encode(before, history, key):
    return base64.urlsafe_b64encode(canonical([1, before, history, key]).encode()).decode()


def decode(cursor, key):
    if not cursor:
        return MAX_ID, []
    try:
        if len(cursor) > 4096:
            raise ValueError
        version, before, history, saved = json.loads(base64.urlsafe_b64decode(cursor).decode())
        _validate(version, before, history, saved, key)
        return before, history
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise ValueError("recurrence cursor scope changed or is invalid; restart") from None


def _validate(version, before, history, saved, key):
    if version != 1 or saved != key or not _valid_id(before):
        raise ValueError
    if not isinstance(history, list) or len(history) > 100:
        raise ValueError
    if any(not _valid_id(item) for item in history):
        raise ValueError


def _valid_id(value):
    return type(value) is int and 1 <= value <= MAX_ID
