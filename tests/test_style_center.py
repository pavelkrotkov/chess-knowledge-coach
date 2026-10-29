"""Source-backed conditional center proxies, not general center labels."""

import chess

from chess_coach.style_center_features import features
from chess_coach.style_center_lines import events
from chess_coach.style_compare import candidates
from chess_coach.style_dimensions import dimensions
from tests.test_style_choices import deep, line
from tests.test_style_transitions import mirror_line


def compare(board, played, alternative):
    return candidates(board, played.split()[0], deep(line(played), line(alternative)))


def test_legal_pawn_exchange_and_contact_for_both_colors():
    board = chess.Board()
    for move in ["e4", "d5", "exd5", "c6"]:
        board.push_san(move)
    exchange = "d5c6 b7c6 g1f3 g8f6"
    retain = "g1f3 g8f6 d2d4 b8d7"
    for position, first, second in [
        (board, exchange, retain),
        (board.mirror(), mirror_line(exchange), mirror_line(retain)),
    ]:
        result = compare(position, first, second)
        assert result["status"] == "comparable"
        choice = dimensions(result["pairs"])
        assert choice["center_contact"] == "contact_absent"
        assert choice["center_pawn_capture"] == "capture"
        assert choice["center_pawn_exchange"] == "exchange"
        root = result["pairs"][0]["root"]
        assert root["center_contacts"]
        capture_events = result["pairs"][0]["played"]["center_events"]
        assert len(capture_events["captures"]) == 1
        assert len(capture_events["exchanges"]) == 1
        assert (
            capture_events["exchanges"][0]["recapture"]["color"]
            != capture_events["exchanges"][0]["first"]["color"]
        )
        inverse = compare(position, second, first)
        assert dimensions(inverse["pairs"])["center_pawn_exchange"] == "no_exchange"


def test_en_passant_captured_square_and_immediate_pawn_recapture():
    board = chess.Board()
    for move in ["e4", "a6", "e5", "d5"]:
        board.push_san(move)
    result = events(board, line("e5d6 e7d6 g1f3 g8f6"))
    assert result["captures"][0]["captured"] == "d5"
    assert result["captures"][0]["to"] == "d6"
    assert result["exchanges"][0]["recapture"]["captured"] == "d6"
    assert [event["color"] for event in result["captures"]] == ["white", "black"]


def test_file_opening_and_exact_locked_skeleton_for_both_colors():
    opening = chess.Board("7k/8/8/3p4/4P3/8/8/K7 w - - 0 1")
    locked = chess.Board("7k/8/8/3pp3/3PP3/8/8/K7 w - - 0 1")
    unlocked = chess.Board("7k/8/8/3pp3/3P4/4P3/8/K7 w - - 0 1")
    cases = [
        (
            opening,
            "e4d5 h8g7 a1b1 g7f6",
            "a1b1 h8g7 b1c1 g7f6",
            "center_file_opening",
            "file_opened",
        ),
        (locked, "d4e5 h8g7 a1b1 g7h6", "a1b1 h8g7 b1c1 g7f6", "center_lock", "skeleton_left"),
    ]
    cases.append(
        (unlocked, "e3e4 h8g7 a1b1 g7f6", "a1b1 h8g7 b1c1 g7f6", "center_lock", "skeleton_entered")
    )
    assert features(locked)["center_locked"]
    assert not features(unlocked)["center_locked"]
    for board, first, second, dimension, expected in cases:
        for position, left, right in [
            (board, first, second),
            (board.mirror(), mirror_line(first), mirror_line(second)),
        ]:
            result = compare(position, left, right)
            assert result["status"] == "comparable"
            assert dimensions(result["pairs"])[dimension] == expected


def test_transposed_same_endpoints_and_conflicting_contacts():
    board = chess.Board()
    first = "g1f3 g8f6 b1c3 b8c6"
    second = "b1c3 b8c6 g1f3 g8f6"
    result = compare(board, first, second)
    choice = dimensions(result["pairs"])
    assert all(
        choice[name] is None
        for name in (
            "center_contact",
            "center_pawn_capture",
            "center_pawn_exchange",
            "center_file_opening",
            "center_lock",
        )
    )
    result = compare(board, "e2e4 d7d5 g1f3 g8f6", "d2d4 e7e5 g1f3 g8f6")
    assert dimensions(result["pairs"])["center_contact"] == "ambiguous"


def test_capture_not_immediate_exchange():
    board = chess.Board()
    for move in ["e4", "d5"]:
        board.push_san(move)
    result = events(board, line("e4d5 d8d5 g1f3 g8f6"))
    assert len(result["captures"]) == 1
    assert not result["exchanges"]


def test_owned_selected_exchange_reaches_cli_and_private_browser(tmp_path, monkeypatch, capsys):
    import io
    import json
    import sys
    import time

    import chess.engine
    import chess.pgn

    import tests.test_deep_selection as selection_tests
    from chess_coach.cli import main
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep
    from chess_coach.style_report import style_report
    from chess_coach.web import create_app
    from tests.test_deep_execution import DeepEngine, options, use_engine

    pgn = """[Event "Synthetic"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 d5 2. exd5 c6 3. dxc6 bxc6 4. Nf3 Nf6 *
"""
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    played_moves = list(game.mainline_moves())
    monkeypatch.setattr(selection_tests, "PGN", pgn)
    path = tmp_path / "center.sqlite"
    db = selection_tests.setup_game(path, monkeypatch)
    selected = select_deep(db, [1], learner=selection_tests.LEARNER, per_game=100, total=100)
    selection_id = selected["games"][0]["selection_id"]

    class Engine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if len(board.move_stack) == 4:
                paths = ["d5c6 b7c6 g1f3 g8f6", "g1f3 g8f6 d2d4 b8d7"]
                if root_moves:
                    paths = [path for path in paths if path.split()[0] == root_moves[0].uci()]
            else:
                chosen = played_moves[len(board.move_stack)]
                roots = root_moves or [
                    chosen,
                    *[move for move in board.legal_moves if move != chosen][: multipv - 1],
                ]
                paths = []
                for move in roots:
                    replay = board.copy()
                    moves = [move]
                    replay.push(move)
                    for _ in range(3):
                        if replay.is_game_over():
                            break
                        next_move = next(iter(replay.legal_moves))
                        moves.append(next_move)
                        replay.push(next_move)
                    paths.append(" ".join(move.uci() for move in moves))
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": [chess.Move.from_uci(uci) for uci in path.split()],
                    "nodes": 200,
                    "depth": 5,
                    "time": 0.05,
                }
                for path in paths
            ]

    use_engine(monkeypatch, Engine(db))
    run_deep(
        db, selection_id, learner=selection_tests.LEARNER, options=options(multipv=2, max_jobs=20)
    )
    started = time.perf_counter()
    report = style_report(db, selection_tests.LEARNER)
    assert time.perf_counter() - started < 15
    matching = [
        item
        for item in report["observations"]
        if item["choices"]["center_pawn_exchange"] == "exchange"
    ]
    assert len(matching) == 1
    chosen = matching[0]
    assert chosen["context"]["color"] == "white"
    assert (
        chosen["pairs"][0]["played"]["center_events"]["exchanges"][0]["recapture"]["color"]
        == "black"
    )
    assert report["dimensions"]["center_pawn_exchange"]["opportunities"] == 1
    assert not report["dimensions"]["center_pawn_exchange"]["sufficient"]
    position_id = chosen["position_id"]
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(path), "style-choices", "--learner", selection_tests.LEARNER],
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["version"] == "style-choices-v4"
    assert cli["dimensions"]["center_pawn_exchange"]["choices"] == {"exchange": 1}
    assert "opponent moves" in cli["center_method"]
    app = create_app(
        db_path=path,
        subject=selection_tests.LEARNER,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/style-choices", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/style-choices",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
    )
    assert page.status_code == 200
    assert (
        b"Central pawn contact" in page.data and b"Consecutive central pawn exchange" in page.data
    )
    assert f"/decisions/{position_id}".encode() in page.data
    assert b"white d5c6" in page.data and b"black b7c6" in page.data


def test_opponent_capture_is_attributed_to_the_actual_mover():
    board = chess.Board()
    for move in ["e4", "d5"]:
        board.push_san(move)
    capture = "g1f3 d5e4 f3g5 g8f6"
    quiet = "b1c3 g8f6 g1f3 b8c6"
    for position, first, second, opponent in [
        (board, capture, quiet, "black"),
        (board.mirror(), mirror_line(capture), mirror_line(quiet), "white"),
    ]:
        result = compare(position, first, second)
        assert result["status"] == "comparable"
        assert dimensions(result["pairs"])["center_pawn_capture"] == "capture"
        records = result["pairs"][0]["played"]["center_events"]["captures"]
        assert len(records) == 1 and records[0]["color"] == opponent and records[0]["ply"] == 2
