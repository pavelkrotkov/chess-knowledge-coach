"""Bounded endpoint choices retain legal history and expose uncertainty."""

import chess

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.style_compare import candidates
from chess_coach.style_dimensions import dimensions
from chess_coach.style_history import selected_boards
from chess_coach.style_history_lines import history_safe, lines_safe
from chess_coach.style_report import style_report
from tests.test_deep_selection import LEARNER, PGN
from tests.test_style_choices import deep, line


def board_and_lines():
    board = chess.Board()
    for san in ["e4", "e5", "d4", "exd4", "Qxd4", "Nc6", "Qe3", "Nf6", "Bd3", "d5", "exd5"]:
        board.push_san(san)
    return board, "d8e7 e3e7 f8e7 g1f3", "f8e7 d5c6 e8g8 g1f3"


def mirror_line(pv):
    def mirror(uci):
        move = chess.Move.from_uci(uci)
        return chess.Move(
            chess.square_mirror(move.from_square),
            chess.square_mirror(move.to_square),
            promotion=move.promotion,
        ).uci()

    return " ".join(mirror(uci) for uci in pv.split())


def test_legal_same_search_queenless_endpoints_for_both_colors():
    board, trade, retain = board_and_lines()
    for position, first, second in [
        (board, trade, retain),
        (board.mirror(), mirror_line(trade), mirror_line(retain)),
    ]:
        assert lines_safe(position, [line(first), line(second)])
        result = candidates(position, first.split()[0], deep(line(first), line(second)))
        assert result["status"] == "comparable"
        assert dimensions(result["pairs"])["queenless"] == "queenless"
        reverse = candidates(position, second.split()[0], deep(line(second), line(first)))
        assert dimensions(reverse["pairs"])["queenless"] == "both_queens"
        assert (
            candidates(position, first.split()[0], deep(line(first), line(second, depth=6)))[
                "status"
            ]
            == "unequal_search_depth"
        )


def test_low_material_one_queen_and_conflicting_alternatives():
    root = {"queens": 2, "one_queen_each": True, "pieces": 6}
    high = {
        "queens": 2,
        "one_queen_each": True,
        "pieces": 6,
        "material": 0,
        "enemy_half_attacks": 0,
    }
    low = {"queens": 0, "pieces": 4, "material": 0, "enemy_half_attacks": 0}
    imbalance = {**high, "queens": 1, "one_queen_each": False}
    pair = {"root": root, "played": low, "alternative": high}
    assert dimensions([pair])["low_material_transition"] == "fewer_than_six_pieces"
    assert (
        dimensions([{**pair, "played": high, "alternative": low}])["low_material_transition"]
        == "six_or_more_pieces"
    )
    assert dimensions([{**pair, "alternative": imbalance}])["queenless"] == "ambiguous"
    assert (
        dimensions([pair, {**pair, "alternative": {**high, "queens": 0, "one_queen_each": False}}])[
            "queenless"
        ]
        == "queenless"
    )
    conflict = {**pair, "played": high, "alternative": low}
    assert dimensions([pair, conflict])["queenless"] == "ambiguous"
    assert (
        dimensions([{**pair, "root": {"queens": 0, "pieces": 4}}])["low_material_transition"]
        is None
    )


def test_history_repetition_draw_and_promotion_are_suppressed():
    board = chess.Board()
    for san in ["Nf3", "Nf6", "Ng1"]:
        board.push_san(san)
    assert history_safe(board)
    assert not lines_safe(board, [line("f6g8")])
    board.push_san("Ng8")
    assert not history_safe(board)
    fifty = chess.Board("7k/8/8/8/8/8/R7/K7 w - - 99 1")
    assert not history_safe(fifty)
    promotion = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
    assert not lines_safe(promotion, [line("a7a8q")])


def test_replay_rejects_custom_roots_and_keeps_standard_history():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    standard = db.connection.execute("SELECT id FROM positions WHERE game_id=1").fetchall()
    boards = selected_boards(db, 1, {row[0] for row in standard})
    assert len(boards) == len(standard)
    assert max(len(board.move_stack) for board in boards.values()) > 0
    custom = '[Event "Synthetic custom"]\n[SetUp "1"]\n[FEN "8/8/8/8/8/2k5/8/K7 w - - 0 1"]\n\n1. Ka2 *\n'
    ingest_pgn(db, custom)
    assert selected_boards(db, 2, set()) == {}
    assert not style_report(db, LEARNER)["observations"]


def test_owned_queenless_choice_reaches_cli_and_private_browser(tmp_path, monkeypatch, capsys):
    import json
    import sys
    import time

    import chess.engine

    import tests.test_deep_selection as selection_tests
    from chess_coach.cli import main
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep
    from chess_coach.web import create_app
    from tests.test_deep_execution import DeepEngine, options, use_engine

    pgn = """[Event "Synthetic"]
[White "fixture_opponent"]
[Black "fixture_learner"]
[Result "*"]

1. e4 e5 2. d4 exd4 3. Qxd4 Nc6 4. Qe3 Nf6 5. Bd3 d5 6. exd5 Qe7
7. Qxe7+ Bxe7 8. Nf3 *
"""
    monkeypatch.setattr(selection_tests, "PGN", pgn)
    path = tmp_path / "transitions.sqlite"
    db = selection_tests.setup_game(path, monkeypatch)
    selected = select_deep(db, [1], learner=LEARNER, per_game=100, total=100)
    selection_id = selected["games"][0]["selection_id"]

    class Engine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if len(board.move_stack) == 11:
                paths = ["d8e7 e3e7 f8e7 g1f3", "f8e7 d5c6 e8g8 g1f3"]
                if root_moves:
                    paths = [path for path in paths if path.split()[0] == root_moves[0].uci()]
            else:
                roots = root_moves or list(board.legal_moves)[:multipv]
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
    run_deep(db, selection_id, learner=LEARNER, options=options(multipv=2, max_jobs=20))
    from chess_coach import style_history

    replay = style_history.decisions
    calls = []

    def counted(*args):
        calls.append(1)
        return replay(*args)

    monkeypatch.setattr(style_history, "decisions", counted)
    started = time.perf_counter()
    report = style_report(db, LEARNER)
    elapsed = time.perf_counter() - started
    assert len(calls) == 1
    assert elapsed < 15
    choices = [item for item in report["observations"] if item["choices"]["queenless"]]
    assert len(choices) == 1 and choices[0]["choices"]["queenless"] == "queenless"
    assert report["dimensions"]["queenless"]["opportunities"] == 1
    assert not report["dimensions"]["queenless"]["sufficient"]
    position_id = choices[0]["position_id"]
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["dimensions"]["queenless"]["choices"] == {"queenless": 1}
    assert "not observed outcomes" in cli["transition_method"]
    app = create_app(
        db_path=path,
        subject=LEARNER,
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
    assert b"Queenless endpoints" in page.data and b"Low-material transition proxy" in page.data
    assert f"/decisions/{position_id}".encode() in page.data


def test_legal_low_material_transition_for_both_colors():
    board = chess.Board("8/8/4k3/3q4/3Q4/8/R6r/4KNN1 w - - 0 1")
    low = "d4d5 e6d5 e1d1 d5e4"
    high = "d4d3 d5d7 e1d1 e6f6"
    for position, first, second in [
        (board, low, high),
        (board.mirror(), mirror_line(low), mirror_line(high)),
    ]:
        result = candidates(position, first.split()[0], deep(line(first), line(second)))
        assert result["status"] == "comparable"
        assert dimensions(result["pairs"])["low_material_transition"] == "fewer_than_six_pieces"
        reverse = candidates(position, second.split()[0], deep(line(second), line(first)))
        assert dimensions(reverse["pairs"])["low_material_transition"] == "six_or_more_pieces"


def test_custom_root_is_counted_as_unavailable_in_owned_report(tmp_path, monkeypatch):
    import tests.test_deep_selection as selection_tests
    from chess_coach.deep_selection import select_deep

    custom = """[Event "Synthetic"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[SetUp "1"]
[FEN "8/8/8/8/8/2k3r1/8/K6R w - - 0 1"]
[Result "*"]

1. Ka2 *
"""
    monkeypatch.setattr(selection_tests, "PGN", custom)
    db = selection_tests.setup_game(tmp_path / "custom.sqlite", monkeypatch)
    selection = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    assert selection["selected"] == 1
    report = style_report(db, LEARNER)
    assert report["selection_counts"]["history_unavailable"] == 1
    assert not report["observations"]
