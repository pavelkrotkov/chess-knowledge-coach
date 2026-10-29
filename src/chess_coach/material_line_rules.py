"""Validate a short exact engine line and reject unsupported continuation moves."""

MAX_LINE_PLIES = 4


def eligible_moves(line, expected):
    if not isinstance(line, dict) or line.get("status") != "limited":
        return None
    if not _exact_line(line):
        return None
    raw = line["pv"].split()[:MAX_LINE_PLIES]
    moves = raw[: len(raw) - len(raw) % 2]
    if len(moves) < 2 or (expected is not None and moves[0] != expected):
        return None
    return moves


def valid_start(board):
    return not board.is_check() and board.ep_square is None and not board.is_repetition(2)


def valid_step(board, move):
    return (
        move in board.legal_moves
        and not move.promotion
        and not board.is_en_passant(move)
        and not board.gives_check(move)
    )


def valid_end(board):
    return not board.is_game_over() and not board.is_repetition(2) and not board.is_fifty_moves()


def _exact_line(line):
    return (
        line.get("score_kind") == "cp"
        and line.get("score_bound") == "exact"
        and isinstance(line.get("pv"), str)
    )
