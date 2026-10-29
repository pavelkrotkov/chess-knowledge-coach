"""Keep the nominated original piece through the defensive move."""


def same_piece(board, after, original, square):
    return (
        original is not None and original.color == board.turn and after.piece_at(square) == original
    )
