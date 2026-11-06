"""Record ordered public moves and supported post-move pawn geometry."""

from .named_structures import match_structures
from .opening_reference_play import _playable
from .opening_storage import position_key

PARENT_PLIES = 40
WINDOW_PLIES = 12
STORED_PLIES = PARENT_PLIES + WINDOW_PLIES


def moves_for(game):
    board = game.board()
    moves, positions = [], []
    for move in game.mainline_moves():
        if not _playable(board, move, len(moves)):
            return None
        parent, san = position_key(board), board.san(move)
        moves.append(move.uci())
        board.push(move)
        if len(moves) <= STORED_PLIES:
            shapes = sorted({(item["family"], item["color"]) for item in match_structures(board)})
            positions.append((len(moves), parent, san, move.uci(), shapes))
    outcome = board.outcome(claim_draw=False)
    if not moves or (outcome is not None and outcome.result() != game.headers["Result"]):
        return None
    return moves, positions
