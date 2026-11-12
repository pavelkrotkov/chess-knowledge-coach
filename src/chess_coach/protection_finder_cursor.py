"""Sign a private, source-scoped finder continuation."""

from itsdangerous import BadData, URLSafeSerializer

from .recurrence_cursor import MAX_ID
from .related_mate_search_token import fingerprint


def _valid(state, scope):
    if not isinstance(state, list) or len(state) != 6 or state[0] != scope:
        return False
    phase, watermark, upper, last, lower = state[1:]
    return (
        type(phase) is int
        and phase in (0, 1)
        and all(type(value) is int for value in (watermark, upper, last, lower))
        and 0 <= lower < last <= upper <= watermark <= MAX_ID
    )


def state_for(secret, subject, corpus, cursor, *, watermark=MAX_ID):
    scope = fingerprint(secret, "protection-finder", [subject, corpus])
    signer = URLSafeSerializer(secret, salt="protection-finder-v2")
    if not cursor:
        return signer, [scope, 0, watermark, watermark, watermark, 0]
    try:
        state = signer.loads(cursor) if len(cursor) <= 1024 else None
        if not _valid(state, scope):
            raise ValueError
        return signer, state
    except (BadData, TypeError, ValueError):
        raise ValueError("finder continuation changed; restart") from None
