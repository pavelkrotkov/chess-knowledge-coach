"""Require a supported short supplied continuation without immediate material loss."""

from .material_line_replay import replay_line
from .material_lines import material


def non_losing(board, line):
    moves = line[:4]
    moves = moves[: len(moves) - len(moves) % 2]
    replay = replay_line(board, moves, allow_checks=False)
    return replay is not None and material(replay[0], board.turn) >= material(board, board.turn)
