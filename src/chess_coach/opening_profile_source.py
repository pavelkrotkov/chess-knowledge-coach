"""Resolve a profile for a verified owned decision and explicit public source."""

import json
import sqlite3
import time

from .opening_fit_later import SECONDS
from .opening_profile_owned_control import control
from .opening_profile_read import profile as broadcast_profile
from .style_time_candidates import verified
from .style_time_query import load_game


def profile(db, root, subject, decision, move, reference, deadline):
    if reference == "broadcast":
        return broadcast_profile(
            root, subject, decision["catalog"]["parent"], move, expires=deadline, extended=True
        )
    if reference != "recent":
        return None
    try:
        game = load_game(db.connection, decision["game_id"])
        if verified(game, subject) != decision["color"] or not 1 <= decision["ply"] <= 20:
            return None
        if (decision["ply"] % 2 == 1) != (decision["color"] == "white"):
            return None
        if time.monotonic() >= deadline:
            return None
        from .opening_profile_recent import profile as recent_profile

        return recent_profile(root, subject, decision, move, control(game), deadline)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        TimeoutError,
        sqlite3.Error,
        json.JSONDecodeError,
    ):
        return None


def deadline(reference):
    return time.monotonic() + SECONDS if reference == "recent" else None
