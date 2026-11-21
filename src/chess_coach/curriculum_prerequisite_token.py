"""Sign and revalidate the one owner-bound prerequisite diagnostic launch."""

import base64
import binascii
import json

from .curriculum_cursor_signature import authentic, sign
from .curriculum_prerequisite_mate import prompt
from .curriculum_prerequisite_source import POLICY, graph
from .fact_fingerprint import canonical, digest

MAX_BYTES = 4096


def issue(db, state, subject, item):
    key_fen = prompt(db, subject, item["corpus_version"], item["puzzle_id"])
    if key_fen != item["prompt_key"]:
        raise ValueError("diagnostic source changed")
    # The signed body contains only the source digest, never an owned game ID.
    data = [
        POLICY,
        graph(),
        state["prerequisite_scope"],
        state["subject_hash"],
        item["corpus_version"],
        item["puzzle_id"],
        digest(key_fen),
        state["revision"],
        state["scan_limit"],
    ]
    raw = canonical(data).encode()
    if len(raw) + 32 > MAX_BYTES:
        raise ValueError("diagnostic token too large")
    return base64.urlsafe_b64encode(sign(db, raw) + raw).decode("ascii")


def _decode(db, token):
    if not isinstance(token, str) or len(token) > 2 * MAX_BYTES:
        raise ValueError("invalid diagnostic token")
    try:
        encoded = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        if not 32 < len(encoded) <= MAX_BYTES:
            raise ValueError("invalid diagnostic token")
        signature, raw = encoded[:32], encoded[32:]
        if not authentic(db, raw, signature):
            raise ValueError("invalid diagnostic token")
        data = json.loads(raw)
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise ValueError("invalid diagnostic token") from None
    if not isinstance(data, list) or len(data) != 9:
        raise ValueError("invalid diagnostic token")
    return data
