"""A synthetic owned source reaches the private check-response report."""

import io
import json
import sys

import chess
import chess.engine
import chess.pgn

import tests.test_deep_selection as selection_tests
from chess_coach.cli import main
from chess_coach.deep_execution_worker import run_deep
from chess_coach.deep_selection import select_deep
from chess_coach.style_report import style_report
from chess_coach.web import create_app
from tests.test_deep_execution import DeepEngine, options, use_engine

PGN = """[Event "Synthetic"]
[White "fixture_opponent"]
[Black "fixture_learner"]
[Result "*"]

1. e4 d5 2. exd5 Qxd5 3. Nc3 Qa5 4. Bb5+ c6 5. Bxc6+ bxc6 6. Nf3 *
"""


def synthetic_paths(board, roots):
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
        paths.append(moves)
    return paths


def test_source_linked_defense_choices_in_cli_and_private_browser(tmp_path, monkeypatch, capsys):
    game = chess.pgn.read_game(io.StringIO(PGN))
    assert game is not None
    played = list(game.mainline_moves())
    monkeypatch.setattr(selection_tests, "PGN", PGN)
    path = tmp_path / "defense.sqlite"
    db = selection_tests.setup_game(path, monkeypatch)
    learner = selection_tests.LEARNER
    selection = select_deep(db, [1], learner=learner, per_game=100, total=100)
    selection_id = selection["games"][0]["selection_id"]

    class Engine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            roots = root_moves or [played[len(board.move_stack)]]
            if root_moves is None and len(board.move_stack) == 7:
                roots = [chess.Move.from_uci("c7c6"), chess.Move.from_uci("e8d8")]
            elif root_moves is None:
                roots += [move for move in board.legal_moves if move not in roots][: multipv - 1]
            return [
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": path,
                    "nodes": 200,
                    "depth": 5,
                    "time": 0.05,
                }
                for path in synthetic_paths(board, roots)
            ]

    use_engine(monkeypatch, Engine(db))
    run_deep(db, selection_id, learner=learner, options=options(multipv=2, max_jobs=20))
    report = style_report(db, learner)
    matches = [item for item in report["observations"] if item["played_move"] == "c7c6"]
    assert len(matches) == 1
    choice = matches[0]
    assert choice["context"]["color"] == "black" and choice["context"]["in_check"]
    assert choice["choices"]["defense_interpose"] == "interposition"
    assert choice["choices"]["defense_king"] == "non_king_move"
    assert report["selection_counts"]["selected_in_check"] >= 1
    assert report["selection_counts"]["comparable_in_check"] >= 1
    assert report["dimensions"]["defense_interpose"]["opportunities"] >= 1
    position_id = choice["position_id"]
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", learner]
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["version"] == "style-choices-v7"
    assert cli["dimensions"]["defense_king"]["choices"]["non_king_move"] >= 1
    assert "not independent" in cli["defense_method"]
    app = create_app(
        db_path=path,
        subject=learner,
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
        b"Interpositions to check" in page.data and b"interposes against the checker" in page.data
    )
    assert f"/decisions/{position_id}".encode() in page.data

    from chess_coach.db import Database

    db = Database(path)
    foreign = style_report(db, "different learner")
    assert not foreign["observations"]
    assert foreign["dimensions"]["defense_king"]["opportunities"] == 0
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=?",
        (position_id,),
    )
    db.connection.commit()
    stale = style_report(db, learner)
    assert stale["selection_counts"]["stale_selection"] > 0
    assert stale["dimensions"]["defense_interpose"]["opportunities"] == 0
    db.close()
