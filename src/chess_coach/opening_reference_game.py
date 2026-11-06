"""Validate one complete public reference game and retain its opening."""

import hashlib

from .opening_reference_url import site as _site
from .opening_reference_validate import valid as _valid
from .opening_storage import position_key

MAX_PLIES = 40


def _moves(game):
    board = game.board()
    positions, moves, seen = [], [], set()
    for move in game.mainline_moves():
        if move not in board.legal_moves:
            return None
        key = position_key(board)
        if len(moves) < MAX_PLIES and key not in seen:
            positions.append((key, board.san(move), move.uci()))
            seen.add(key)
        moves.append(move.uci())
        board.push(move)
    return (moves, positions) if moves else None


def record(game, raw, number):
    if not _valid(game, raw) or not (played := _moves(game)):
        return None
    moves, positions = played
    context = {
        key: game.headers.get(key, "?")[:200]
        for key in ("Event", "Date", "White", "Black", "Result")
    }
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
    return identity, number, context, site, positions
