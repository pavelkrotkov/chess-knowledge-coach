"""Keep a nominal game control only when it agrees with the original PGN."""

import io

import chess.pgn

from .opening_fit_owned_summary import _control


def control(game):
    headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
    stored = _control(game["time_control"])
    if headers is None or _control(headers.get("TimeControl")) != stored:
        return "unknown"
    return stored
