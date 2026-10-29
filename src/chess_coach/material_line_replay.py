"""Replay legal moves and require displayed checks to have a reply."""

from .material_line_positions import valid_end, valid_step


def replay_line(board, moves, *, allow_checks, minimum_plies=2):
    replay = board.copy()
    san = []
    used = []
    for text in moves:
        try:
            move = replay.parse_uci(text)
        except ValueError:
            return None
        if not valid_step(replay, move, allow_checks=allow_checks):
            return None
        san.append(replay.san(move))
        used.append(text)
        replay.push(move)
        if not valid_end(replay):
            return None
        if _resolved(replay, used, allow_checks, minimum_plies):
            break
    if replay.is_check() or len(used) < minimum_plies:
        return None
    return replay, used, san


def _resolved(board, used, allow_checks, minimum_plies):
    return (
        allow_checks and len(used) >= minimum_plies and len(used) % 2 == 0 and not board.is_check()
    )
