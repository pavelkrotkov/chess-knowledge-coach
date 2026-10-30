"""Find a qualified proof for the same named pin identities."""

import chess

from .pin_proof import proven


def matching(board, move, pinned, rear, kind):
    return next(
        (
            item
            for item in proven(board, move)
            if (item["type"], item["pinned"], item["rear"])
            == (kind, chess.square_name(pinned), chess.square_name(rear))
        ),
        None,
    )
