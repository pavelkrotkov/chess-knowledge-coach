"""Bind a fork-attempt keyset cursor to the private subject."""

from .related_mate_search_token import VERSION, decode, encode, fingerprint

KIND = "fork-attempts-v1"


def pack(secret, subject, row):
    return encode(
        secret,
        {
            "version": VERSION,
            "kind": KIND,
            "subject": fingerprint(secret, KIND, subject),
            "started_at": row["started_at"],
            "attempt_id": row["attempt_id"],
        },
    )


def _text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit


def unpack(secret, subject, cursor):
    if not cursor:
        return None
    if not isinstance(cursor, str) or len(cursor) > 1024:
        raise ValueError("fork attempt cursor unavailable")
    state = decode(secret, cursor)
    when, attempt = state.get("started_at"), state.get("attempt_id")
    if (
        state.get("kind") != KIND
        or state.get("subject") != fingerprint(secret, KIND, subject)
        or not _text(when, 64)
        or not _text(attempt, 256)
    ):
        raise ValueError("fork attempt cursor unavailable")
    return when, attempt
