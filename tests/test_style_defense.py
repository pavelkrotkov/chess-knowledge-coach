"""Legal check-evasion descriptions, not claims about defensive strength."""

import chess
import pytest

from chess_coach.style_defense_evasion import response


@pytest.mark.parametrize("flip", [False, True])
def test_interposition_and_countercheck_are_overlapping(flip):
    board = chess.Board("4r3/8/1k6/8/8/8/3B4/4K3 w - - 0 1")
    move = chess.Move.from_uci("d2e3")
    if flip:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    assert board.is_valid() and board.is_check() and move in board.legal_moves
    info = response(board, move.uci())
    assert info["interposition"] and info["countercheck"]
    assert not info["capture"] and not info["king_move"]


@pytest.mark.parametrize("flip", [False, True])
def test_king_capture_reports_piece_and_checker_overlap(flip):
    board = chess.Board("k7/8/8/8/8/8/4r3/4K3 w - - 0 1")
    move = chess.Move.from_uci("e1e2")
    if flip:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    assert move in board.legal_moves and board.is_check()
    info = response(board, move.uci())
    assert info["king_move"] and info["capture"] and info["captured_checker"]
    assert info["captured_piece"] == "rook"
    assert info["captured_square"] == chess.square_name(move.to_square)


@pytest.mark.parametrize("flip", [False, True])
def test_en_passant_capture_of_checker(flip):
    board = chess.Board("k7/8/8/3pP3/4K3/8/8/8 w - d6 0 2")
    move = chess.Move.from_uci("e5d6")
    if flip:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    assert board.is_valid() and board.is_check() and board.is_en_passant(move)
    assert move in board.legal_moves
    info = response(board, move.uci())
    assert not info["interposition"] and info["capture"] and info["captured_checker"]
    assert info["captured_piece"] == "pawn"
    assert info["captured_square"] != chess.square_name(move.to_square)


@pytest.mark.parametrize("flip", [False, True])
def test_double_check_has_no_interposition_and_noncheck_is_outside_scope(flip):
    board = chess.Board("4r2k/8/8/8/1b6/8/8/4K3 w - - 0 1")
    if flip:
        board = board.mirror()
    assert len(board.checkers()) == 2
    for move in board.legal_moves:
        info = response(board, move.uci())
        assert info["king_move"] and not info["interposition"]
    assert response(chess.Board(), "e2e4") is None
    with pytest.raises(ValueError):
        response(board, "a1a2")


def test_apparent_en_passant_interposition_has_impossible_check_history():
    board = chess.Board("k5b1/8/8/4pP2/8/1K6/8/8 w - e6 0 2")
    assert board.status() & chess.STATUS_IMPOSSIBLE_CHECK


@pytest.mark.parametrize("flip", [False, True])
def test_capture_does_not_imply_capture_of_checker(flip):
    board = chess.Board("k7/8/8/8/8/8/7b/r6K w - - 0 1")
    move = chess.Move.from_uci("h1h2")
    if flip:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    assert board.is_valid() and move in board.legal_moves
    info = response(board, move.uci())
    assert info["king_move"] and info["capture"] and not info["captured_checker"]
    assert info["captured_piece"] == "bishop"


def continuation(board, move):
    replay = board.copy()
    roots = [move]
    replay.push_uci(move)
    for _ in range(3):
        next_move = next(iter(replay.legal_moves))
        roots.append(next_move.uci())
        replay.push(next_move)
    return " ".join(roots)


@pytest.mark.parametrize("flip", [False, True])
def test_same_search_in_check_comparisons_are_one_vote_per_dimension(flip):
    from chess_coach.style_compare import candidates
    from chess_coach.style_defense_choices import annotate
    from chess_coach.style_dimensions import dimensions
    from tests.test_style_choices import deep, line

    board = chess.Board("4r3/8/1k6/8/8/8/3B4/4K3 w - - 0 1")
    if flip:
        board = board.mirror()
    block = chess.Move.from_uci("d2e3" if not flip else "d7e6").uci()
    king = chess.Move.from_uci("e1f2" if not flip else "e8f7").uci()
    first, second = line(continuation(board, block)), line(continuation(board, king))
    result = candidates(board, block, deep(first, second))
    assert result["status"] == "comparable"
    annotate(board, result)
    vote = dimensions(result["pairs"])
    assert vote["defense_king"] == "non_king_move"
    assert vote["defense_interpose"] == "interposition"
    assert vote["defense_countercheck"] == "countercheck"
    assert vote["defense_capture"] is None
    assert result["pairs"][0]["played"]["defense_response"]["countercheck"]


def test_non_check_and_unsupported_comparisons_do_not_vote():
    from chess_coach.style_compare import candidates
    from chess_coach.style_defense_choices import annotate
    from chess_coach.style_dimensions import dimensions
    from tests.test_style_choices import deep, line

    board = chess.Board()
    first = line("e2e4 e7e5 g1f3 b8c6")
    second = line("d2d4 d7d5 g1f3 g8f6")
    result = candidates(board, "e2e4", deep(first, second))
    annotate(board, result)
    assert all(
        dimensions(result["pairs"])[name] is None
        for name in ("defense_king", "defense_capture", "defense_interpose", "defense_countercheck")
    )
    assert (
        candidates(board, "e2e4", deep(first, line(second["pv"], score=51)))["status"]
        == "no_similar_alternative"
    )
    assert (
        candidates(board, "e2e4", deep(first, line(second["pv"], kind="mate")))["status"]
        == "alternative_score_unusable"
    )


def test_check_context_coverage_keeps_forced_and_unknown_separate():
    from collections import Counter

    from chess_coach.style_defense_coverage import record

    forced = chess.Board("7k/8/7Q/8/8/8/8/K7 b - - 0 1")
    assert forced.is_valid() and forced.is_check() and forced.legal_moves.count() == 1
    counts = Counter()
    record(counts, forced, {"pre_move_fen": forced.fen()}, "forced_move")
    record(counts, chess.Board(), {"pre_move_fen": chess.STARTING_FEN}, "comparable")
    record(counts, None, {"pre_move_fen": chess.STARTING_FEN}, "history_unavailable")
    assert counts["selected_in_check"] == counts["forced_check"] == 1
    assert counts["comparable_in_check"] == 0
    assert counts["outside_check"] == counts["check_context_unknown"] == 1


@pytest.mark.parametrize("flip", [False, True])
def test_capture_and_interposition_are_distinct_legal_responses(flip):
    from chess_coach.style_compare import candidates
    from chess_coach.style_defense_choices import annotate
    from chess_coach.style_dimensions import dimensions
    from tests.test_style_choices import deep, line

    board = chess.Board()
    for san in ("e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "Bb5+"):
        board.push_san(san)
    block = chess.Move.from_uci("c7c6")
    capture = chess.Move.from_uci("a5b5")
    if flip:
        board = board.mirror()
        block = chess.Move(
            chess.square_mirror(block.from_square), chess.square_mirror(block.to_square)
        )
        capture = chess.Move(
            chess.square_mirror(capture.from_square), chess.square_mirror(capture.to_square)
        )
    left = line(continuation(board, block.uci()))
    right = line(continuation(board, capture.uci()))
    compared = candidates(board, block.uci(), deep(left, right))
    assert compared["status"] == "comparable"
    annotate(board, compared)
    votes = dimensions(compared["pairs"])
    assert votes["defense_capture"] == "non_capture"
    assert votes["defense_interpose"] == "interposition"
    other = compared["pairs"][0]["alternative"]["defense_response"]
    assert other["capture"] and other["captured_checker"] and not other["interposition"]


def test_forced_check_and_missing_original_history_cannot_produce_choices():
    from chess_coach.style_compare import candidates
    from chess_coach.style_observation_compare import compare
    from tests.test_style_choices import deep, line

    board = chess.Board("7k/8/7Q/8/8/8/8/K7 b - - 0 1")
    assert board.is_check() and board.legal_moves.count() == 1
    assert candidates(board, "h8g8", deep(line("h8g8")))["status"] == "forced_move"
    status, compared, source, covered, complete = compare(
        None, "fixture", {"pre_move_fen": board.fen()}, {}, None, None
    )
    assert status == "history_unavailable"
    assert compared is None and source is None and not covered and not complete
