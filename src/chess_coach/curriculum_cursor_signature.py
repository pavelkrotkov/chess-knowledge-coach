"""Bind continuation tokens to the current local database."""

import hashlib
import hmac

from .db import Database


def sign(db: Database, payload: bytes) -> bytes:
    key = db.connection.execute(
        "SELECT cursor_key FROM curriculum_source_revision WHERE id=1"
    ).fetchone()[0]
    return hmac.digest(key, payload, hashlib.sha256)


def authentic(db: Database, payload: bytes, signature: bytes) -> bool:
    return hmac.compare_digest(signature, sign(db, payload))
