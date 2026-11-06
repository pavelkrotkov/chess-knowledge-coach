"""Validate one complete public reference game and retain its opening."""

import hashlib

from .opening_reference_metadata import context_for
from .opening_reference_play import moves_for as _moves
from .opening_reference_url import game_site
from .opening_reference_url import site as _site
from .opening_reference_validate import valid as _valid


def record(game, raw, number):
    if not _valid(game, raw) or not (played := _moves(game)):
        return None
    moves, positions = played
    context = context_for(game.headers)
    tags = [
        game.headers.get(k, "?") for k in ("Event", "Date", "Round", "White", "Black", "Result")
    ]
    identity = hashlib.sha256(("\n".join(tags) + "\n" + " ".join(moves)).encode()).hexdigest()
    site = next(
        (
            _site(game.headers.get(k, ""))
            for k in ("GameURL", "BroadcastURL", "Site")
            if _site(game.headers.get(k, ""))
        ),
        "",
    )
    game_url = game_site(game.headers.get("GameURL", ""))
    return identity, number, context, site, positions, game_url
