"""Selected-choice coverage, context confounding and private source links."""

import io
import json
import sys
from typing import Any

import chess
import chess.engine
import chess.pgn

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.deep_execution_worker import run_deep
from chess_coach.deep_selection import select_deep
from chess_coach.ingest import ingest_pgn
from chess_coach.style_compare import candidates
from chess_coach.style_dimensions import dimensions
from chess_coach.style_familiarity import familiarity
from chess_coach.style_metrics import metrics
from chess_coach.style_report import style_report
from chess_coach.style_sources import source_games
from chess_coach.style_summary import summarize
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


def test_comparable_same_search_and_forced_or_missing_choices():
    board = chess.Board("8/8/4k3/3q4/3Q4/8/8/4K3 w - - 0 1")
    played = line("d4d5 e6d5 e1e2 d5e4")
    other = line("d4d3 d5d7 e1e2 e6f6", 30)
    result = candidates(board, "d4d5", deep(played, other))
    assert result["status"] == "comparable"
    assert dimensions(result["pairs"])["simplification"] == "fewer_pieces"
    assert candidates(board, "d4d5", deep(played))["status"] == "single_root_search"
    forced_board = chess.Board("7k/8/6K1/8/8/8/8/8 b - - 0 1")
    assert forced_board.legal_moves.count() == 1
    assert candidates(forced_board, "h8g8", deep(line("h8g8")))["status"] == "forced_move"
    assert (
        candidates(board, "d4d5", deep(other, line("d4e4 e6d6 e1e2 d6c6")))["status"]
        == "played_root_not_covered"
    )
    assert (
        candidates(board, "d4d5", deep(played, line(other["pv"], 51)))["status"]
        == "no_similar_alternative"
    )
    assert (
        candidates(board, "d4d5", deep(played, line("d4d3", 20)))["status"] == "short_or_invalid_pv"
    )
    assert (
        candidates(board, "d4d5", deep(line(played["pv"], kind="mate"), other))["status"]
        == "score_unusable"
    )
    assert candidates(board, "d4d5", deep(played, other, status="unstable"))["status"] == "unstable"
    assert (
        candidates(board, "d4d5", deep(played, line(other["pv"], kind="mate")))["status"]
        == "alternative_score_unusable"
    )


def test_conflicting_alternatives_are_ambiguous_and_attack_map_includes_pinned_piece():
    base = {"material": 0, "pieces": 4, "enemy_half_attacks": 4}
    pairs = [
        {"played": base, "alternative": {**base, "pieces": 2}},
        {"played": base, "alternative": {**base, "pieces": 6}},
    ]
    assert dimensions(pairs)["simplification"] == "ambiguous"
    board = chess.Board("k3r3/8/8/4N3/8/8/8/4K3 w - - 0 1")
    assert all(move.from_square != chess.E5 for move in board.legal_moves)
    assert metrics(board, chess.WHITE)["enemy_half_attacks"] == 4


def test_overlapping_games_never_become_prior_familiarity():
    fen = chess.STARTING_FEN
    rows: list[dict[str, Any]] = [
        {
            "learner_color": "white",
            "pre_move_fen": fen,
            "game_id": 1,
            "observation_at": "2026-01-01T00:00:00+00:00",
            "actual_position_time_for_test": "2026-01-03T00:00:00+00:00",
        },
        {
            "learner_color": "white",
            "pre_move_fen": fen,
            "game_id": 2,
            "observation_at": "2026-01-02T00:00:00+00:00",
            "actual_position_time_for_test": "2026-01-02T00:01:00+00:00",
        },
        {
            "learner_color": "white",
            "pre_move_fen": fen,
            "game_id": 3,
            "observation_at": "2026-01-02T00:00:00+00:00",
        },
    ]
    familiarity(rows, False)
    assert [row["familiarity"] for row in rows] == ["unknown"] * 3
    assert [row["earlier_started_games_with_position"] for row in rows] == [0, 1, 1]
    assert all("prior_observed_games" not in row for row in rows)
    familiarity(rows, True)
    assert all(row["earlier_started_games_with_position"] is None for row in rows)
    rows[0]["observation_at"] = None
    familiarity(rows, False)
    assert rows[0]["familiarity"] == "unknown"
    assert rows[0]["earlier_started_games_with_position"] is None
    familiarity(rows, True)
    assert all(row["familiarity"] == "unknown" for row in rows)
    assert all(row["earlier_started_games_with_position"] is None for row in rows)


def _observation(game, color, clock, choice):
    return {
        "game_id": game,
        "allocation": "control",
        "choices": {
            "simplification": choice,
            "material_activity": None,
            "queenless": None,
            "low_material_transition": None,
            "center_contact": None,
            "center_pawn_capture": None,
            "center_pawn_exchange": None,
            "center_file_opening": None,
            "center_lock": None,
            "root_check": None,
            "conditional_check": None,
            "conditional_mate": None,
            "defense_king": None,
            "defense_capture": None,
            "defense_interpose": None,
            "defense_countercheck": None,
            "protect_move_target": None,
            "protect_capture_attacker": None,
        },
        "context": {
            "color": color,
            "in_check": False,
            "rating": "unknown",
            "opponent_rating": "unknown",
            "time_control": "600+0",
            "clock_band": clock,
            "phase": "high material",
            "familiarity": "unknown",
            "opening": {"name": "unknown"},
            "structures": [],
            "game_start_at": f"2026-01-{game:02d}T00:00:00+00:00",
        },
    }


def test_time_pressure_strata_and_small_samples_are_visible():
    items = [_observation(i, "white", "30 seconds or less", "fewer_pieces") for i in range(1, 4)]
    items += [_observation(i, "black", "over 30 seconds", "more_pieces") for i in range(4, 7)]
    summary = summarize(items)["simplification"]
    assert summary["opportunities"] == 6 and summary["direction"] == "balanced"
    clock = [entry for entry in summary["strata"] if entry["field"] == "clock_band"]
    assert len(clock) == 2 and all(not entry["sufficient"] for entry in clock)
    assert {tuple(entry["choices"]) for entry in clock} == {("fewer_pieces",), ("more_pieces",)}
    assert summary["trend"] is None


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
    assert cli_report["version"] == "style-choices-v7"
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


def test_empty_profile_and_both_learner_colors(tmp_path, monkeypatch):
    empty = Database(":memory:")
    empty.initialize()
    report = style_report(empty, LEARNER)
    assert report["coverage"]["decisions"] == 0
    assert not report["observations"]
    assert all(not dim["sufficient"] for dim in report["dimensions"].values())
    db, _ = prepare_selected(tmp_path / "black.sqlite", monkeypatch, per_game=1)
    selection = select_deep(db, [1], learner=OPPONENT, per_game=3, total=3)
    selected = selection["games"][0]["selection_id"]
    use_engine(monkeypatch, FourPlyEngine(db))
    run_deep(db, selected, learner=OPPONENT, options=options(max_jobs=3))
    black = style_report(db, OPPONENT)
    assert black["coverage"]["decisions"] == 6
    assert black["selection_counts"]["comparable"] > 0
    assert all(item["context"]["color"] == "black" for item in black["observations"])
    assert all(item["played_line"]["score_pov"] == "black" for item in black["observations"])


def test_material_attack_tradeoff_and_conflict():
    played = {"material": 2, "pieces": 8, "enemy_half_attacks": 4}
    active = {"material": 1, "pieces": 8, "enemy_half_attacks": 7}
    assert (
        dimensions([{"played": played, "alternative": active}])["material_activity"]
        == "more_material"
    )
    inverse = {"material": 3, "pieces": 8, "enemy_half_attacks": 1}
    result = dimensions(
        [{"played": played, "alternative": active}, {"played": played, "alternative": inverse}]
    )
    assert result["material_activity"] == "ambiguous"


def test_stale_selection_suppresses_observations(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "stale.sqlite", monkeypatch, per_game=2)
    use_engine(monkeypatch, FourPlyEngine(db))
    run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=2))
    assert style_report(db, LEARNER)["selection_counts"]["comparable"] > 0
    db.connection.execute(
        "UPDATE pipeline_stages SET status='failed' WHERE game_id=1 AND stage='analysis'"
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["selection_counts"]["stale_selection"] == 2
    assert not report["observations"]


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


def test_trend_requires_two_sufficient_dated_independent_periods():
    items = []
    for game_id in range(1, 7):
        choice = "fewer_pieces" if game_id <= 3 else "more_pieces"
        items.extend([_observation(game_id, "white", "over 30 seconds", choice) for _ in range(2)])
    result = summarize(items)["simplification"]["trend"]
    assert result is not None
    assert result["earlier"]["choices"] == {"fewer_pieces": 6}
    assert result["later"]["choices"] == {"more_pieces": 6}
    items[0]["context"]["game_start_at"] = None
    assert summarize(items)["simplification"]["trend"] is None


def test_material_balance_is_from_the_mover_perspective():
    board = chess.Board("7k/8/8/8/8/8/P7/K7 w - - 0 1")
    assert metrics(board, chess.WHITE)["material"] == 1
    assert metrics(board, chess.BLACK)["material"] == -1


def test_game_start_does_not_prove_prior_position_in_real_ingestion():
    db = Database(":memory:")
    db.initialize()
    # The first game may still be in progress when the second reaches this position.
    for day in ("01", "02"):
        tags = f'[UTCDate "2026.01.{day}"]\n[UTCTime "00:00:00"]\n'
        ingest_pgn(db, PGN.replace('[Event "Synthetic"]\n', f'[Event "Synthetic {day}"]\n{tags}'))
    source = source_games(db, LEARNER)
    assert source["independent_games"] == 2
    first_moves = [game["contexts"][0] for game in source["games"]]
    by_start = sorted(first_moves, key=lambda context: context["observation_at"])
    assert [item["familiarity"] for item in by_start] == ["unknown", "unknown"]
    assert [item["earlier_started_games_with_position"] for item in by_start] == [0, 1]
    assert all("prior_observed_games" not in item for item in by_start)
