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


def test_duplicate_imports_do_not_count_as_independent_games(monkeypatch):
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
    from chess_coach import style_schedule_nomination, style_schedule_nomination_game
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.style_schedule_budget import history_budget
    from chess_coach.style_schedule_candidates import allocate
    from chess_coach.style_schedule_nomination import prioritize
    from chess_coach.style_schedule_scan import read_games

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    checked = PGN[: PGN.index("1. e4")] + "1. d4 c6 2. e4 Qa5+ 3. Ke2 *\n"
    ingest_pgn(db, checked)
    games = [
        (db.connection.execute("SELECT * FROM games WHERE id=?", (i,)).fetchone(), color)
        for i, color in ((1, "white"), (2, "white"))
    ]
    with history_budget() as budget:
        budget["limit"] = 12
        ordered, coverage = prioritize(db, games, 0)
        assert ordered[0][0]["id"] == 2
        assert coverage["nomination_games"] == 1
        assert coverage["nomination_turns"] == 1
        assert coverage["structural_nomination_games"] == 1
        assert coverage["structural_nomination_turns"] == 1
        assert coverage["structural_nomination_prioritized"]
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
        assert coverage["structural_replayed_positions"] == 1
        assert coverage["structural_target_selected"]
    # A plausible FEN is not proof that the recorded move or game is valid.
    db.connection.execute("UPDATE positions SET uci='a1a1' WHERE game_id=2 AND ply=5")
    ordered, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 1 and ordered[0][0]["id"] == 1
    with history_budget() as budget:
        budget["limit"] = 100
        candidates, skipped, _, _, reconstructed = read_games(db, ordered, 0)
        assert skipped == 1 and reconstructed == 1
        assert not any(item["in_check"] for item in candidates)
    db.connection.execute("UPDATE positions SET uci='e1e2' WHERE game_id=2 AND ply=5")
    after_fen = db.connection.execute(
        "SELECT fen FROM positions WHERE game_id=2 AND ply=5"
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE positions SET fen=(SELECT fen FROM positions WHERE game_id=2 AND ply=4) "
        "WHERE game_id=2 AND ply=5"
    )
    ordered, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 1 and ordered[0][0]["id"] == 1
    db.connection.execute("UPDATE positions SET fen=? WHERE game_id=2 AND ply=5", (after_fen,))
    db.connection.commit()
    forced = PGN.replace('White "fixture_learner"', 'White "fixture_opponent"')
    forced = forced.replace('Black "fixture_opponent"', 'Black "fixture_learner"')
    forced = forced[: forced.index("1. e4")] + "1. e4 f6 2. Qh5+ g6 *\n"
    ingest_pgn(db, forced)
    forced_game = db.connection.execute("SELECT * FROM games WHERE id=3").fetchone()
    ordered, coverage = prioritize(db, [(forced_game, "black"), games[1]], 0)
    assert ordered[0][0]["id"] == 2 and coverage["nomination_games"] == 1
    # Another legal nonforced check has only interpositions: it remains a
    # fallback, while a genuinely different legal response gets priority.
    same = PGN.replace('White "fixture_learner"', 'White "fixture_opponent"')
    same = same.replace('Black "fixture_opponent"', 'Black "fixture_learner"')
    same = same[: same.index("1. e4")] + "1. e4 d5 2. Bb5+ c6 *\n"
    ingest_pgn(db, same)
    same_game = db.connection.execute("SELECT * FROM games WHERE id=4").fetchone()
    ordered, coverage = prioritize(db, [(same_game, "black"), games[1]], 0)
    assert ordered[0][0]["id"] == 2 and coverage["nomination_games"] == 2
    assert coverage["structural_nomination_games"] == 1
    assert coverage["structural_nomination_turns"] == 1
    assert coverage["structural_nomination_prioritized"]
    from chess_coach.style_defense_nomination import distinct
    from chess_coach.style_schedule_game import game_candidates
    from chess_coach.style_schedule_target import target as choose_target

    different_board = chess.Board()
    for san in ("d4", "c6", "e4", "Qa5+"):
        different_board.push_san(san)
    assert distinct(different_board, different_board.parse_san("Ke2")) is True
    capture_board = chess.Board("rnbq1bnr/p2ppkpp/5p2/1pp5/2B1P3/5P1P/PPPP2PR/RNBQK1N1 b Q - 2 7")
    assert capture_board.is_valid() and capture_board.is_check()
    assert distinct(capture_board, capture_board.parse_uci("f7e8")) is True
    from chess_coach.style_defense_evasion import response as defense_response

    assert not defense_response(capture_board, "f7e8")["capture"]
    assert defense_response(capture_board, "b5c4")["capture"]
    same_board = chess.Board()
    for san in ("e4", "d5", "Bb5+"):
        same_board.push_san(san)
    assert distinct(same_board, same_board.parse_san("c6")) is False
    forced_board = chess.Board()
    for san in ("e4", "f6", "Qh5+"):
        forced_board.push_san(san)
    assert distinct(forced_board, forced_board.parse_san("g6")) is False
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_defense_nomination.lines_safe", lambda *_: False)
        assert distinct(different_board, different_board.parse_san("Ke2")) is None
        _, unknown_coverage = prioritize(db, games, 0)
        assert unknown_coverage["structural_nomination_unknown_turns"] == 1
        assert not unknown_coverage["structural_nomination_prioritized"]
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_defense_nomination.MAX_MOVES", 0)
        assert distinct(different_board, different_board.parse_san("Ke2")) is None
    replayed = game_candidates(db, same_game, "black") + game_candidates(db, games[1][0], "white")
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.style_schedule_rotation.rank",
            lambda _key, _kind, game, position: (-game, position),
        )
        chosen, structural, unknown = choose_target(db, learner_key(LEARNER), 0, replayed)
        assert chosen["game_id"] == 2 and structural == 1 and unknown == 0
        fallback_target, _, _ = choose_target(db, learner_key(LEARNER), 1, replayed)
        assert fallback_target["game_id"] == 4
    # In one fully replayed game, choose the structurally distinct later root
    # instead of two earlier same-category check evasions on priority cycles.
    two_checks = PGN[: PGN.index("1. e4")] + (
        "1. Na3 c6 2. d4 Qa5+ 3. b4 Qxb4+ 4. Qd2 a5 5. Qxb4 a4 "
        "6. f3 Ra5 7. Qb6 Rh5 8. Qd8+ Kxd8 9. Kf2 d6 10. Bd2 e5 "
        "11. Kg3 Rh3+ 12. Kf2 *\n"
    )
    ingest_pgn(db, two_checks)
    combined_game = db.connection.execute("SELECT * FROM games WHERE id=5").fetchone()
    same_game_roots = game_candidates(db, combined_game, "white")
    checks = [item for item in same_game_roots if item["in_check"]]
    assert [item["structural_defense"] for item in checks] == [False, False, True]
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.style_schedule_rotation.rank",
            lambda _key, _kind, game, position: (game, position),
        )
        priority_root, count, _ = choose_target(db, learner_key(LEARNER), 0, same_game_roots)
        fallback_root, _, _ = choose_target(db, learner_key(LEARNER), 1, same_game_roots)
    assert count == 1 and priority_root["position_id"] == checks[-1]["position_id"]
    assert fallback_root["position_id"] == checks[0]["position_id"]
    fallback, coverage = prioritize(db, games, 1)
    assert fallback[0][0]["id"] == 1 and not coverage["nomination_prioritized"]
    fallback, _ = prioritize(db, games, 3)
    assert fallback[0][0]["id"] == 2
    db.connection.execute("DELETE FROM positions WHERE game_id=2 AND ply=4")
    ordered, coverage = prioritize(db, games, 0)
    assert ordered[0][0]["id"] == 1 and coverage["nomination_unknown_games"] == 1
    assert coverage["nomination_games"] == 0
    # A deadline during a game leaves that game and the rest unchecked.
    calls = iter((False, True, True))
    with monkeypatch.context() as patch:
        patch.setattr(style_schedule_nomination, "reached", lambda: next(calls))
        patch.setattr(style_schedule_nomination_game, "reached", lambda: next(calls))
        _, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 0
    assert coverage["nomination_unchecked_games"] == 2
    db.close()
