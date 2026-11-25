"""Sign a v7 goal/window envelope around the unchanged v6 plan state."""

import base64
import binascii
import json

from .curriculum_cursor_codec import MAX_CURSOR_BYTES
from .curriculum_cursor_signature import authentic, sign
from .curriculum_cursor_validation import validate_state
from .curriculum_window_validate import validate
from .fact_fingerprint import canonical


def encode(db, value):
    validate(value)
    validate_state(value["state"], allow_full=True)
    raw = canonical(value).encode()
    if len(raw) + 32 > MAX_CURSOR_BYTES:
        raise ValueError("practice window cursor is too large")
    return base64.urlsafe_b64encode(sign(db, raw) + raw).decode("ascii")


def decode(db, token):
    try:
        if not isinstance(token, str) or len(token) > 2 * MAX_CURSOR_BYTES:
            raise ValueError("invalid practice window cursor")
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        if not 32 < len(raw) <= MAX_CURSOR_BYTES or not authentic(db, raw[32:], raw[:32]):
            raise ValueError("invalid practice window cursor")
        value = json.loads(raw[32:])
        validate(value)
        validate_state(value["state"], allow_full=True)
        return value
    except (ValueError, TypeError, UnicodeError, binascii.Error, KeyError, AttributeError):
        raise ValueError("invalid practice window cursor") from None
