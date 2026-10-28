"""Encode and validate bounded curriculum continuation tokens."""

import base64
import binascii
import json

from .curriculum_cursor_signature import authentic, sign
from .curriculum_cursor_validation import validate_state
from .db import Database
from .fact_fingerprint import canonical

MAX_CURSOR_BYTES = 16384


def encode_cursor(db: Database, state: dict) -> str:
    validate_state(state)
    raw = canonical(state).encode()
    if len(raw) + 32 > MAX_CURSOR_BYTES:
        raise ValueError("curriculum cursor exceeds the supported size")
    signature = sign(db, raw)
    return base64.urlsafe_b64encode(signature + raw).decode("ascii")


def decode_cursor(db: Database, value: str) -> dict:
    if not isinstance(value, str) or len(value) > MAX_CURSOR_BYTES * 2:
        raise ValueError("invalid curriculum cursor")
    try:
        raw = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
        if len(raw) > MAX_CURSOR_BYTES:
            raise ValueError("invalid curriculum cursor")
        if len(raw) <= 32:
            raise ValueError("invalid curriculum cursor")
        signature, payload = raw[:32], raw[32:]
        if not authentic(db, payload, signature):
            raise ValueError("invalid curriculum cursor")
        state = json.loads(payload)
        validate_state(state)
        return state
    except (ValueError, TypeError, UnicodeError, binascii.Error, KeyError, OverflowError):
        raise ValueError("invalid curriculum cursor") from None
