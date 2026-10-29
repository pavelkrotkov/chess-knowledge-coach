"""Checking observations use legal moves and conditional, source-bound claims."""

import chess
import pytest

from chess_coach.mate_proof_moves import immediate_mates
from chess_coach.style_check_annotate import annotate
from chess_coach.style_check_choices import classify
from chess_coach.style_check_lines import events
from chess_coach.style_check_mate import witness
from chess_coach.style_compare import candidates
from chess_coach.style_dimensions import dimensions
from tests.test_style_choices import deep, line
from tests.test_style_transitions import mirror_line


def compared(board, played, other):
    result = candidates(board, played.split()[0], deep(line(played), line(other)))
    if result["status"] == "comparable":
        annotate(board, result, None)
    return result


def mirrored(board, *lines, flip):
    return (board.mirror(), *(mirror_line(item) for item in lines)) if flip else (board, *lines)


@pytest.mark.parametrize("flip", [False, True])
def test_root_check_lists_all_evasions_and_opponent_checks(flip):
    board = chess.Board("4kb2/r7/8/8/2n5/7R/8/7K w - - 0 1")
    position, check, quiet = mirrored(
        board, "h3e3 c4e3 h1g1 a7a1", "h1g1 e8f7 h3h4 a7a1", flip=flip
    )
    result = compared(position, check, quiet)
    assert result["status"] == "comparable"
    assert dimensions(result["pairs"])["root_check"] == "check"
    first = result["pairs"][0]["played"]["check_events"]["checks"][0]
    after = position.copy()
    after.push_uci(check.split()[0])
    assert {item["uci"] for item in first["evasions"]["moves"]} == {
        move.uci() for move in after.legal_moves
    }
    assert first["evasions"]["count"] == 7
    evasions = first["evasions"]["moves"]
    assert any(item["king_move"] for item in evasions)
    assert any(item["capture"] for item in evasions)
    assert any(not item["king_move"] and not item["capture"] for item in evasions)
    opponent = result["pairs"][0]["played"]["check_events"]["checks"][-1]
    assert opponent["ply"] == 4 and opponent["color"] != first["color"]
    reverse = compared(position, quiet, check)
    assert dimensions(reverse["pairs"])["root_check"] == "no_check"


@pytest.mark.parametrize("flip", [False, True])
def test_actual_root_in_check_never_becomes_attack_vote(flip):
    board = chess.Board("r6k/8/8/8/8/8/8/K4R2 w - - 0 1")
    position, first, second = mirrored(
        board, "a1b1 a8b8 b1c2 h8g7", "a1b2 a8a7 b2c3 h8g7", flip=flip
    )
    assert position.is_check()
    result = compared(position, first, second)
    assert result["status"] == "comparable"
    choice = dimensions(result["pairs"])
    assert (
        result["pairs"][0]["played"]["check_events"]["conditional_mate"]["status"]
        == "root_in_check"
    )
    assert all(
        choice[name] == "ambiguous"
        for name in ("root_check", "conditional_check", "conditional_mate")
    )


@pytest.mark.parametrize("flip", [False, True])
def test_conditional_learner_check_is_distinct_from_root(flip):
    board = chess.Board()
    for san in ["e4", "e5", "Bc4", "Nc6"]:
        board.push_san(san)
    position, first, second = mirrored(
        board, "g1f3 g8f6 c4f7 e8f7", "g1h3 g8f6 b1c3 f8c5", flip=flip
    )
    result = compared(position, first, second)
    assert result["status"] == "comparable"
    assert dimensions(result["pairs"])["root_check"] is None
    assert dimensions(result["pairs"])["conditional_check"] == "check"
    event = result["pairs"][0]["played"]["check_events"]["checks"][0]
    assert event["ply"] == 3 and not event["response"]
    assert event["color"] == ("black" if flip else "white")


@pytest.mark.parametrize("flip", [False, True])
def test_checking_response_to_opponent_is_not_attacking_choice(flip):
    board = chess.Board("4kb2/r7/8/8/2n5/7R/8/7K w - - 0 1")
    position, first, second = mirrored(
        board, "h1g2 c4e3 h3e3 e8d8", "h3h4 e8f7 h1g1 a7a1", flip=flip
    )
    result = compared(position, first, second)
    assert result["status"] == "comparable"
    choice = dimensions(result["pairs"])
    assert choice["conditional_check"] == "ambiguous"
    assert choice["conditional_mate"] == "ambiguous"
    checking = result["pairs"][0]["played"]["check_events"]["checks"]
    assert checking[0]["ply"] == 2 and checking[0]["color"] == ("white" if flip else "black")
    assert checking[1]["ply"] == 3 and checking[1]["response"]


@pytest.mark.parametrize("flip", [False, True])
def test_legal_mate_witness_is_conditional_on_a_specific_reply(flip):
    board = chess.Board()
    board.push_san("f3")
    position, first, second = mirrored(
        board, "e7e5 g2g4 a7a6 b1c3", "g8f6 g2g4 b8c6 b1c3", flip=flip
    )
    played = events(position, line(first))
    other = events(position, line(second))
    assert played["conditional_mate"]["status"] == "complete"
    assert played["conditional_mate"]["moves"]
    conditional_board = position.copy()
    for move in first.split()[:2]:
        conditional_board.push_uci(move)
    assert played["conditional_mate"]["moves"] == immediate_mates(conditional_board)
    assert not other["conditional_mate"]["moves"]
    pair = {
        "root": {"in_check": False},
        "played": {"check_events": played},
        "alternative": {"check_events": other},
    }
    assert classify(pair)["conditional_mate"] == "mate_available_after_reply"
    # This is a legal proof exercise only: it does not invent engine scores or a comparable source.


def test_mate_unknowns_and_false_witnesses():
    assert witness(chess.Board())["moves"] == immediate_mates(chess.Board()) == []
    in_check = chess.Board("r6k/8/8/8/8/8/8/K4R2 w - - 0 1")
    assert witness(in_check)["status"] == "in_check"
    promotion = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
    assert witness(promotion)["status"] == "promotion_unsupported"
    draw = chess.Board("7k/8/8/8/8/8/R7/K7 w - - 99 1")
    assert witness(draw)["status"] == "history_unsupported"


@pytest.mark.parametrize(
    "kind,depth,score,expected",
    [
        ("mate", 5, 0, "score_unusable"),
        ("cp", 3, 0, "score_unusable"),
        ("cp", 5, 51, "no_similar_alternative"),
    ],
)
def test_native_scores_remain_strictly_gated(kind, depth, score, expected):
    board = chess.Board()
    played = line("e2e4 e7e5 g1f3 b8c6", kind=kind, depth=depth)
    other = line("d2d4 d7d5 g1f3 g8f6", score=score)
    assert candidates(board, "e2e4", deep(played, other))["status"] == expected


def test_evasion_budget_is_unknown_not_a_check_vote(monkeypatch):
    from chess_coach import style_check_evasions

    board = chess.Board("4kb2/r7/8/8/2n5/7R/8/7K w - - 0 1")
    check, quiet = "h3e3 c4e3 h1g1 a7a1", "h1g1 e8f7 h3h4 a7a1"
    monkeypatch.setattr(style_check_evasions, "MAX_MOVES", 0)
    result = compared(board, check, quiet)
    event = result["pairs"][0]["played"]["check_events"]["checks"][0]
    assert event["evasions"]["status"] == "budget_exceeded"
    assert event["evasions"]["count"] is None
    assert dimensions(result["pairs"])["root_check"] == "ambiguous"


def test_owned_checking_choice_reaches_cli_and_private_browser(tmp_path, monkeypatch, capsys):
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

1. e4 d5 2. exd5 Qxd5 3. Nc3 Qa5 4. Bb5+ c6 5. Bxc6+ bxc6 6. Nf3 *
"""
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    played_moves = list(game.mainline_moves())
    monkeypatch.setattr(selection_tests, "PGN", pgn)
    path = tmp_path / "checking.sqlite"
    db = selection_tests.setup_game(path, monkeypatch)
    selected = select_deep(db, [1], learner=selection_tests.LEARNER, per_game=100, total=100)
    selection_id = selected["games"][0]["selection_id"]

    class Engine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if len(board.move_stack) == 6:
                paths = ["f1b5 c7c6 b5c6 b7c6", "g1f3 g8f6 f1c4 c7c6"]
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
        if item["played_move"] == "f1b5" and item["choices"]["root_check"] == "check"
    ]
    assert len(matching) == 1
    choice = matching[0]
    assert choice["context"]["color"] == "white" and not choice["context"]["in_check"]
    event = choice["pairs"][0]["played"]["check_events"]["checks"][0]
    assert event["color"] == "white" and event["ply"] == 1
    assert any(move["uci"] == "c7c6" for move in event["evasions"]["moves"])
    assert report["dimensions"]["root_check"]["opportunities"] >= 1
    assert not report["dimensions"]["root_check"]["sufficient"]
    position_id = choice["position_id"]
    import importlib

    report_module = importlib.import_module("chess_coach.style_report")
    monkeypatch.setattr(report_module, "MATE_SEARCH_LIMIT", 1)
    limited = style_report(db, selection_tests.LEARNER)
    assert limited["checking_coverage"]["examined"] == 1
    assert (
        limited["checking_coverage"]["completed"] + limited["checking_coverage"]["unsupported"] == 1
    )
    assert limited["checking_coverage"]["skipped"] > 0
    for dimension in ("root_check", "conditional_check"):
        assert limited["dimensions"][dimension] == report["dimensions"][dimension]
    for item in limited["observations"]:
        for pair in item["pairs"]:
            states = [
                pair[side]["check_events"]["conditional_mate"]["status"]
                for side in ("played", "alternative")
            ]
            if "report_budget_exhausted" in states:
                assert item["choices"]["conditional_mate"] == "ambiguous"
    again = style_report(db, selection_tests.LEARNER)
    assert again["checking_coverage"] == limited["checking_coverage"]
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(path), "style-choices", "--learner", selection_tests.LEARNER],
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["version"] == "style-choices-v6"
    assert cli["dimensions"]["root_check"]["choices"]["check"] >= 1
    assert "not forced threats" in cli["checking_method"]
    assert cli["checking_coverage"]["examined"] == 1
    assert cli["checking_coverage"]["skipped"] > 0
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
        b"Root checking choices" in page.data
        and b"Conditional immediate-mate witnesses" in page.data
    )
    assert f"/decisions/{position_id}".encode() in page.data
    assert b"Bb5+" in page.data and b"legal evasions" in page.data
    assert b"additional continuation boards skipped as unknown" in page.data


def test_conditional_mate_budget_is_unknown_not_absent(monkeypatch):
    from chess_coach import style_check_mate

    monkeypatch.setattr(style_check_mate, "MAX_MOVES", 0)
    bounded = witness(chess.Board())
    assert bounded == {"status": "budget_exceeded", "moves": []}
    info = {"checks": [], "pre_third_in_check": False, "conditional_mate": bounded}
    pair = {
        "root": {"in_check": False},
        "played": {"check_events": info},
        "alternative": {"check_events": info},
    }
    assert classify(pair)["conditional_mate"] == "ambiguous"


def test_root_check_strata_separate_response_contexts():
    from chess_coach.style_summary import summarize
    from tests.test_style_choices import _observation

    choice = _observation(1, "white", "over 30 seconds", None)
    response = _observation(2, "black", "30 seconds or less", None)
    choice["choices"]["root_check"] = "check"
    response["choices"]["root_check"] = "ambiguous"
    response["context"]["in_check"] = True
    rows = [
        row
        for row in summarize([choice, response])["root_check"]["strata"]
        if row["field"] == "in_check"
    ]
    by_status = {row["value"]: row for row in rows}
    assert by_status[False]["opportunities"] == 1
    assert by_status[True]["opportunities"] == 0 and by_status[True]["ambiguous"] == 1


def test_report_budget_accounts_for_unsupported_and_skipped_witnesses():
    budget = {"limit": 1, "examined": 0, "completed": 0, "unsupported": 0, "skipped": 0}
    promotion = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
    assert witness(promotion, budget)["status"] == "promotion_unsupported"
    assert budget == {"limit": 1, "examined": 1, "completed": 0, "unsupported": 1, "skipped": 0}
    assert witness(chess.Board(), budget)["status"] == "report_budget_exhausted"
    assert budget["skipped"] == 1 and budget["completed"] == 0
