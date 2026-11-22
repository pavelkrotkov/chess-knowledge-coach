"""Yield recorded roots before legal alternatives from replayed positions."""


def roots(positions):
    for ply, board, recorded in positions:
        yield ply, board, recorded, recorded
    for ply, board, recorded in reversed(positions):
        for move in board.legal_moves:
            if move != recorded:
                yield ply, board, recorded, move
