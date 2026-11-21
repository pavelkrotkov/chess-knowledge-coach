"""Conservative quiet-move and immediate-reply scope for owned fork misses."""

from .fork_defense_safety import quiet_after, safe_material
from .fork_proof import MAX_REPLIES
from .material_exchange_rules import unclear


def supported(board, move):
    if not _start(board, move):
        return False
    after = quiet_after(board, move)
    if after is None or unclear(after):
        return False
    return safe_material(after) and _replies(after)


def _start(board, move):
    return bool(
        move
        and move in board.legal_moves
        and board.ep_square is None
        and not board.is_castling(move)
        and not unclear(board)
    )


def _replies(board):
    replies = list(board.legal_moves)
    return 0 < len(replies) <= MAX_REPLIES and all(_ordinary(board, reply) for reply in replies)


def _ordinary(board, reply):
    return not (
        board.gives_check(reply)
        or board.is_en_passant(reply)
        or board.is_castling(reply)
        or reply.promotion is not None
    )
