"""Prepare the versioned ordered profile index without replacing v1."""

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .opening_profile_play import moves_for
from .opening_profile_store import store
from .opening_reference_game import record
from .opening_reference_games import collect
from .opening_reference_index import _build

INDEX_NAME = "opening-reference-broadcast-2026-09-v2.sqlite"


def _record(game, raw, number):
    result = record(game, raw, number, play=moves_for)
    if result is None:
        return None
    # Conservatively collapse repeat imports with the same players and full moves.
    moves = [move.uci() for move in game.mainline_moves()]
    identity = digest(
        canonical(
            {
                "white": normalize_identity(game.headers.get("White")),
                "black": normalize_identity(game.headers.get("Black")),
                "moves": moves,
            }
        )
    )
    return (identity, *result[1:], len(moves))


def _collect(text, truncated):
    return collect(text, truncated, parser=_record)


def build(root, subject):
    return _build(root, subject, INDEX_NAME, _collect, store)
