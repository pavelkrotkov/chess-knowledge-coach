"""Check that a legal fork line captures an original target."""

from .puzzle_session_validate import legal_move


def target_captured(board, first, squares, line):
    after = board.copy()
    after.push(first)
    after.push_uci(line[1])
    capture = legal_move(after, line[2])
    return (
        capture.from_square == first.to_square
        and capture.to_square in squares
        and after.is_capture(capture)
        and after.piece_at(capture.to_square) == board.piece_at(capture.to_square)
    )
