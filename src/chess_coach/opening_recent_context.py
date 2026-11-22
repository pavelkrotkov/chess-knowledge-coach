"""Retain supplied rated-game context without inferring actual thinking time."""

from .opening_fit_context_index import _record as profile_record
from .opening_fit_owned_summary import _control


def _rating(headers, key):
    value = headers.get(key, "")
    return int(value) if value.isascii() and value.isdecimal() and 0 < int(value) < 5000 else None


def _berserk(headers):
    values = [
        str(headers.get(key, "")).strip().casefold()
        for key in ("Berserk", "WhiteBerserk", "BlackBerserk")
    ]
    if "berserk" in str(headers.get("Event", "")).casefold() or any(
        value in {"1", "yes", "true"} for value in values
    ):
        return "yes"
    return "unknown"


def record(game, raw, number, *, check=None):
    value = profile_record(game, raw, number, check=check)
    if value is None:
        return None
    headers = game.headers
    event = headers.get("Event", "")
    rated = True if event.startswith("Rated ") else (False if event.startswith("Casual ") else None)
    control = _control(headers.get("TimeControl"))
    value[2].update(
        TimeControl=control if control != "unknown" else None,
        WhiteElo=_rating(headers, "WhiteElo"),
        BlackElo=_rating(headers, "BlackElo"),
        Variant=headers.get("Variant"),
        rated=rated,
        berserk=_berserk(headers),
    )
    return value
