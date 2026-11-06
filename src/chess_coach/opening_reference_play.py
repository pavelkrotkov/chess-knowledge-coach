"""Validate a bounded played line and index its opening positions."""

from .opening_storage import position_key

MAX_PLIES = 40
MAX_GAME_PLIES = 512


def _playable(board, move, count):
    return (
        count < MAX_GAME_PLIES
        and board.outcome(claim_draw=False) is None
        and move in board.legal_moves
    )


def moves_for(game):
    board = game.board()
    positions, moves, seen = [], [], set()
    for move in game.mainline_moves():
        if not _playable(board, move, len(moves)):
            return None
        key = position_key(board)
        if len(moves) < MAX_PLIES and key not in seen:
            positions.append((key, board.san(move), move.uci()))
            seen.add(key)
        moves.append(move.uci())
        board.push(move)
    outcome = board.outcome(claim_draw=False)
    if not moves or (outcome is not None and outcome.result() != game.headers["Result"]):
        return None
    return moves, positions
