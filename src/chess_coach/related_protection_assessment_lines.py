"""Validate the exact selected protection line against its setup history."""

from .puzzle_session_validate import legal_move


def selected(board, selected_lines):
    if not isinstance(selected_lines, list) or not selected_lines:
        raise ValueError("protection assessment line unavailable")
    line = selected_lines[0]
    if not isinstance(line, str) or not 1 <= len(line.split()) <= 64:
        raise ValueError("protection assessment line unavailable")
    replay = board.copy(stack=True)
    moves = []
    for text in line.split():
        move = legal_move(replay, text)
        moves.append(move)
        replay.push(move)
    return line, moves[0]
