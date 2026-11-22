"""Build a separate pinned ordered index preserving supplied time controls."""

from functools import partial

from .opening_profile_index import _record as profile_record
from .opening_profile_store import TRANSFORM as PREVIOUS_TRANSFORM
from .opening_profile_store import store
from .opening_reference_games import collect
from .opening_reference_index import _build

INDEX_NAME = "opening-reference-broadcast-2026-09-v3.sqlite"
TRANSFORM = PREVIOUS_TRANSFORM.replace("v2:", "v3:", 1) + ";time-control-context"


def _record(game, raw, number, *, check=None):
    record = profile_record(game, raw, number, check=check)
    if record is None:
        return None
    value = game.headers.get("TimeControl")
    if isinstance(value, str) and len(value) <= 200:
        record[2]["TimeControl"] = value
    return record


def _collect(text, truncated):
    return collect(text, truncated, parser=_record)


def build(root, subject):
    return _build(root, subject, INDEX_NAME, _collect, partial(store, transform=TRANSFORM))
