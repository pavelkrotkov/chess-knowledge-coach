import chess

from chess_coach.motifs import detect_motifs


def test_detects_fork_and_hanging_piece() -> None:
    board = chess.Board("4k3/8/8/8/8/2N5/8/4K3 w - - 0 1")
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    board.set_piece_at(chess.C5, chess.Piece(chess.ROOK, chess.BLACK))
    board.set_piece_at(chess.F6, chess.Piece(chess.BISHOP, chess.BLACK))

    motifs = detect_motifs(board)

    names = {fact["motif"] for fact in motifs}
    assert "fork" in names
    assert all(fact["detector_version"] == "0.1.0" for fact in motifs)


def test_empty_position_has_no_opportunities() -> None:
    assert detect_motifs(chess.Board()) == []
