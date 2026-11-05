"""Selected-choice coverage, context confounding and private source links."""

import io
import json
import sys

import chess
import chess.engine
import chess.pgn

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.deep_execution_worker import run_deep
from chess_coach.ingest import ingest_pgn
from chess_coach.style_report import style_report
from chess_coach.web import create_app
from tests.test_deep_execution import DeepEngine, options, prepare_selected, use_engine
from tests.test_deep_selection import LEARNER, OPPONENT, PGN


def line(pv, score=0, *, kind="cp", depth=5):
    return {
        "root_move": pv.split()[0],
        "pv": pv,
        "score_kind": kind,
        "score_value": score,
        "score_bound": "exact",
        "depth": depth,
        "status": "limited",
    }


def deep(*lines, status="complete"):
    return {"status": status, "result": {"alternatives": [{"line": item} for item in lines]}}


class FourPlyEngine(DeepEngine):
    def analyse(self, board, limit, multipv, root_moves=None):
        game = chess.pgn.read_game(io.StringIO(PGN))
        assert game is not None
        played = list(game.mainline_moves())[len(board.move_stack)]
        roots = root_moves or [
            played,
            *[m for m in board.legal_moves if m != played][: multipv - 1],
        ]
        values = []
        for move in roots:
            position = board.copy()
            pv = [move]
            position.push(move)
            for _ in range(3):
                next_move = next(iter(position.legal_moves))
                pv.append(next_move)
                position.push(next_move)
            values.append(
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": pv,
                    "nodes": 200,
                    "depth": 5,
                    "time": 0.05,
                }
            )
        return values


def test_profile_uses_owned_current_deep_results_and_private_browser(tmp_path, monkeypatch, capsys):
    path = tmp_path / "style.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=6)
    use_engine(monkeypatch, FourPlyEngine(db))
    run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=6))
    report = style_report(db, LEARNER)
    assert report["coverage"]["decisions"] == 6
    assert report["selection_counts"]["selected"] == 6
    assert report["selection_counts"]["selection_eligible"] == 6
    assert report["selection_counts"]["selection_capped_out"] == 0
    assert report["selection_counts"]["comparable"] > 0
    item = report["observations"][0]
    assert item["selection_id"] == selection_id and item["analysis_run_id"]
    assert item["played_line"]["root_move"] == item["played_move"]
    assert item["context"]["familiarity"] == "unknown"
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    output = capsys.readouterr().out
    cli_report = json.loads(output)
    assert cli_report["version"] == "style-choices-v11"
    assert "not prior exposure" in cli_report["familiarity_note"]
    assert "overlapping games" in cli_report["trend_note"]
    assert LEARNER not in output and OPPONENT not in output
    assert "game_key" not in output and "fingerprint" not in output
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
    assert page.status_code == 200 and b"Source choices" in page.data
    assert f"/decisions/{item['position_id']}".encode() in page.data


def test_duplicate_imports_do_not_count_as_independent_games():
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    ingest_pgn(db, PGN.replace('Event "Synthetic"', 'Event "Second import"'))
    report = style_report(db, LEARNER)
    assert report["coverage"]["examined_games"] == 2
    assert report["coverage"]["independent_games"] == 1
    assert report["coverage"]["duplicate_games"] == 1
    assert report["coverage"]["familiarity_history_incomplete"]
    assert report["coverage"]["decisions"] == 6
    assert report["coverage"]["outcomes"] == {"unknown": 1}

    # A bounded schedule can prioritize a checked turn only after full replay.
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.style_schedule_budget import history_budget
    from chess_coach.style_schedule_candidates import allocate
    from chess_coach.style_schedule_nomination import prioritize
    from chess_coach.style_schedule_scan import read_games

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    checked = PGN.replace('White "fixture_learner"', 'White "fixture_opponent"')
    checked = checked.replace('Black "fixture_opponent"', 'Black "fixture_learner"')
    checked = checked[: checked.index("1. e4")] + "1. e4 d5 2. Bb5+ c6 *\n"
    ingest_pgn(db, checked)
    games = [
        (db.connection.execute("SELECT * FROM games WHERE id=?", (i,)).fetchone(), color)
        for i, color in ((1, "white"), (2, "black"))
    ]
    with history_budget() as budget:
        budget["limit"] = 12
        ordered, coverage = prioritize(db, games, 0)
        assert ordered[0][0]["id"] == 2
        assert coverage["nomination_games"] == 1
        assert coverage["nomination_turns"] == 1
        candidates, _, _, exhausted, reconstructed = read_games(db, ordered, 0)
        assert reconstructed == 1 and exhausted
        assert any(item["in_check"] and item["status"] == "ready" for item in candidates)
        assert budget["used"] == 12
    with history_budget() as budget:
        budget["limit"] = 12
        coverage, slots, _ = allocate(db, LEARNER, learner_key(LEARNER), 0)
        assert coverage["nomination_games"] == 1
        assert coverage["reconstructed_games"] == 1 and coverage["history_budget_exhausted"]
        assert dict(slots)["target"]["game_id"] == 2
    # A plausible FEN is not proof that the recorded move or game is valid.
    db.connection.execute("UPDATE positions SET uci='a1a1' WHERE game_id=2 AND ply=4")
    ordered, coverage = prioritize(db, games, 0)
    with history_budget() as budget:
        budget["limit"] = 12
        candidates, skipped, _, _, reconstructed = read_games(db, ordered, 0)
        assert skipped == 1 and reconstructed == 0 and not candidates
    db.connection.execute("UPDATE positions SET uci='c7c6' WHERE game_id=2 AND ply=4")
    db.connection.commit()
    forced = checked.replace("1. e4 d5 2. Bb5+ c6", "1. e4 f6 2. Qh5+ g6")
    ingest_pgn(db, forced)
    forced_game = db.connection.execute("SELECT * FROM games WHERE id=3").fetchone()
    ordered, coverage = prioritize(db, [(forced_game, "black"), games[1]], 0)
    assert ordered[0][0]["id"] == 2 and coverage["nomination_games"] == 1
    fallback, coverage = prioritize(db, games, 1)
    assert fallback[0][0]["id"] == 1 and not coverage["nomination_prioritized"]
    fallback, _ = prioritize(db, games, 3)
    assert fallback[0][0]["id"] == 2
    db.connection.execute("DELETE FROM positions WHERE game_id=2 AND ply=3")
    ordered, coverage = prioritize(db, games, 0)
    assert ordered[0][0]["id"] == 1 and coverage["nomination_unknown_games"] == 1
    assert coverage["nomination_games"] == 0
    db.close()
