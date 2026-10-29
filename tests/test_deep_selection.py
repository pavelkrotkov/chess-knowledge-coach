"""Manual selection is bounded, reproducible and never produces mastery evidence."""

import json
import sys

import chess
import chess.engine
import pytest

from chess_coach.analysis import merge_analysis_outputs
from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.deep_selection import select_deep
from chess_coach.deep_selection_reasons import decision_reasons
from chess_coach.deep_selection_views import list_selections, show_selection
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app

LEARNER = "fixture_learner"
OPPONENT = "fixture_opponent"
PGN = """[Event "Synthetic"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 d6 5. c3 Be7 6. O-O O-O *
"""


class Engine:
    def __init__(self):
        self.id = {"name": "Synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        ply = len(board.move_stack)
        played = root_moves is not None
        move = root_moves[0] if played else next(iter(board.legal_moves))
        score = chess.engine.Cp(0)
        if ply == 0 and not played:
            score = chess.engine.Cp(300)
        if ply == 4:
            score = chess.engine.Mate(3)
        wdl = chess.engine.Wdl(500, 200, 300)
        if ply == 6 and not played:
            wdl = chess.engine.Wdl(900, 50, 50)
        result = {
            "score": chess.engine.PovScore(score, board.turn),
            "pv": [move],
            "wdl": chess.engine.PovWdl(wdl, board.turn),
            "nodes": 100,
            "depth": 5,
        }
        if ply == 2:
            result["lowerbound"] = True
        return [result]

    def quit(self):
        pass


def setup_game(path, monkeypatch, *, count=1):
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    for number in range(count):
        ingest_pgn(db, PGN.replace('Event "Synthetic"', f'Event "Synthetic {number}"'))
        game_id = number + 1
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        result = run_analysis(
            db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
        )
        assert result["status"] == "complete"
    return db


def named_motifs(board):
    return [{"motif": "fork"}] if len(board.move_stack) == 0 else []


def test_bounded_replay_context_reasons_and_no_mastery(tmp_path, monkeypatch):
    from chess_coach import deep_selection_reasons

    db = setup_game(tmp_path / "selection.sqlite", monkeypatch)
    monkeypatch.setattr(deep_selection_reasons, "detect_motifs", named_motifs)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _: pytest.fail("selector reran engine")
    )
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    first = select_deep(db, [1], learner=LEARNER, per_game=4, total=4)
    again = select_deep(db, [1], learner=LEARNER, per_game=4, total=4)
    assert first == again
    detail = show_selection(db, 1, LEARNER)
    assert detail["state"] == "current" and detail["coverage"]["eligible"] == 6
    assert detail["coverage"]["control_target"] == 1 and detail["coverage"]["selected"] == 4
    assert detail["coverage"]["nominated"]["score"] == 2
    assert detail["coverage"]["nominated"]["uncertain"] == 2
    assert detail["coverage"]["nominated"]["opportunity"] == 1
    assert detail["coverage"]["overlapping_nominations"] == 1
    assert detail["coverage"]["reason_counts"]["cp_score_gap"] == 1
    assert detail["coverage"]["reason_counts"]["wdl_score_gap"] == 1
    assert detail["coverage"]["reason_counts"]["bounded_score"] == 1
    assert detail["coverage"]["reason_counts"]["mate_score"] == 1
    assert detail["coverage"]["reason_counts"]["possible_fork"] == 1
    assert all(
        item["status"] == "pending_deep" and item["ply"] % 2 == 1 for item in detail["items"]
    )
    assert any("control_sample" in item["reasons"] for item in detail["items"])
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    public = json.dumps([first, detail, list_selections(db, LEARNER)])
    assert LEARNER not in public and OPPONENT not in public and "fingerprint" not in public
    assert '"learner_key"' not in public and PGN not in public


def test_tiny_budget_controls_black_side_and_invocation_cap(tmp_path, monkeypatch):
    from chess_coach import deep_selection_reasons

    db = setup_game(tmp_path / "two.sqlite", monkeypatch, count=2)
    monkeypatch.setattr(deep_selection_reasons, "detect_motifs", named_motifs)
    one = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    detail = show_selection(db, 1, LEARNER)
    assert one["selected"] == 1 and detail["items"][0]["allocation"] == "control"
    assert detail["coverage"]["omitted_critical"] > 0
    batch = select_deep(db, [2, 1], learner=LEARNER, per_game=2, total=3)
    assert batch["selected"] <= 3
    assert all(item["coverage"]["selected"] <= 2 for item in batch["games"])
    assert batch == select_deep(db, [1, 2], learner=LEARNER, per_game=2, total=3)
    black = select_deep(db, [1], learner=OPPONENT, per_game=2, total=2)
    assert black["selected"] == 2
    assert all(item["ply"] % 2 == 0 for item in show_selection(db, 1, OPPONENT)["items"])
    assert all(
        "control_sample" in item["reasons"]
        for item in show_selection(db, 1, OPPONENT)["items"]
        if item["allocation"] == "control"
    )


def test_config_generations_stale_detection_and_reactivation(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "history.sqlite", monkeypatch)
    first = select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    first_id = first["games"][0]["selection_id"]
    second = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    assert second["games"][0]["selection_id"] != first_id
    assert show_selection(db, 1, LEARNER, selection_id=first_id)["state"] == "historical"
    assert select_deep(db, [1], learner=LEARNER, per_game=3, total=3) == first
    assert show_selection(db, 1, LEARNER)["selection_id"] == first_id
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 2
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    assert show_selection(db, 1, LEARNER)["state"] == "stale"
    changed = select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    assert changed["games"][0]["selection_id"] != first_id


def test_stale_checkpoint_and_race_do_not_store_selection(tmp_path, monkeypatch):
    from chess_coach import deep_selection_storage

    db = setup_game(tmp_path / "stale.sqlite", monkeypatch)
    original = deep_selection_storage.source_snapshot

    def changed(*args):
        result = original(*args)
        return {**result, "input_fingerprint": "different"}

    with monkeypatch.context() as patch:
        patch.setattr(deep_selection_storage, "source_snapshot", changed)
        report = select_deep(db, [1], learner=LEARNER)
    assert report["games"][0]["status"] == "inputs_changed"
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 0
    db.connection.execute("UPDATE games SET pgn=pgn || ' '")
    db.connection.commit()
    report = select_deep(db, [1], learner=LEARNER)
    assert report["games"][0]["status"] == "unavailable"
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 0


def test_possible_hanging_and_fork_are_observations_not_evidence():
    hanging = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    assert hanging.is_valid()
    reasons = decision_reasons({"uci": "d1d4"}, hanging, {}, 150, 0.1)
    assert "possible_hanging_piece" in reasons and "score_unavailable" in reasons
    fork = chess.Board("4k3/8/2N5/8/1r1q4/8/8/4K3 w - - 0 1")
    assert fork.is_valid()
    reasons = decision_reasons({"uci": "c6b4"}, fork, {}, 150, 0.1)
    assert "possible_fork" in reasons


def test_private_cli_browser_and_handoff_guard(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "private.sqlite"
    db = setup_game(db_path, monkeypatch)
    monkeypatch.setenv("LICHESS_USERNAME", LEARNER)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(db_path),
            "select-deep",
            "--game-id",
            "1",
            "--per-game",
            "2",
            "--total",
            "2",
        ],
    )
    main()
    created = capsys.readouterr().out
    assert json.loads(created)["selected"] == 2
    assert LEARNER not in created and OPPONENT not in created and "fingerprint" not in created
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(db_path), "show-deep-selection", "1"]
    )
    main()
    shown = capsys.readouterr().out
    assert json.loads(shown)["state"] == "current" and LEARNER not in shown
    assert "fingerprint" not in shown and "learner_key" not in shown
    private = tuple(
        db.connection.execute(
            "SELECT learner_key,input_fingerprint,selection_fingerprint FROM deep_selection_runs"
        ).fetchone()
    )
    assert not any(value in created or value in shown for value in private)
    app = create_app(
        db_path=db_path,
        subject=LEARNER,
        actor="fixture-reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/deep-selections/1", base_url="https://coach.invalid").status_code == 403
    headers = {"Tailscale-User-Login": "fixture-login"}
    page = client.get("/deep-selections/1", base_url="https://coach.invalid", headers=headers)
    assert (
        page.status_code == 200 and b"pending deep" in page.data and b"omitted" in page.data.lower()
    )
    assert LEARNER.encode() not in page.data and OPPONENT.encode() not in page.data
    assert not any(value.encode() in page.data for value in private)
    assert (
        client.get(
            "/deep-selections", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )
    target = setup_game(tmp_path / "target.sqlite", monkeypatch)
    target.connection.execute("DELETE FROM analysis_runs")
    target.connection.commit()
    with pytest.raises(ValueError, match="does not support selection or deep history"):
        merge_analysis_outputs(target, db)
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def test_stable_controls_and_source_fingerprint_ignore_local_row_ids(tmp_path, monkeypatch):
    from chess_coach.deep_selection_source import source_snapshot

    first = setup_game(tmp_path / "first.sqlite", monkeypatch)
    second = Database(tmp_path / "second.sqlite")
    second.initialize()
    dummy = PGN.replace("fixture_learner", "dummy_a").replace("fixture_opponent", "dummy_b")
    ingest_pgn(second, dummy)
    ingest_pgn(second, PGN.replace('Event "Synthetic"', 'Event "Synthetic 0"'))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    result = run_analysis(second, 2, game_input(second, 2), config, engine_identity(sys.executable))
    assert result["status"] == "complete"
    left, right = source_snapshot(first, 1, LEARNER), source_snapshot(second, 2, LEARNER)
    assert left["game_key"] == right["game_key"]
    assert left["input_fingerprint"] == right["input_fingerprint"]
    select_deep(first, [1], learner=LEARNER, per_game=3, total=3)
    select_deep(second, [2], learner=LEARNER, per_game=3, total=3)
    left_items, right_items = (
        show_selection(first, 1, LEARNER)["items"],
        show_selection(second, 2, LEARNER)["items"],
    )
    assert [(item["ply"], item["reasons"]) for item in left_items] == [
        (item["ply"], item["reasons"]) for item in right_items
    ]
    assert left_items[0]["position_id"] != right_items[0]["position_id"]


def test_control_sampling_varies_across_games_and_repeats():
    from chess_coach.deep_selection_policy import select_positions
    from chess_coach.fact_fingerprint import digest

    candidates = [
        {"position_id": ply, "ply": ply, "fen": f"position-{ply}", "reasons": []}
        for ply in range(1, 11)
    ]
    chosen = []
    for number in range(20):
        key = digest(f"synthetic-game-{number}")
        first, _ = select_positions(candidates, key, 1)
        again, _ = select_positions(candidates, key, 1)
        assert first == again and first[0]["allocation"] == "control"
        chosen.append(first[0]["ply"])
    assert len(set(chosen)) > 1


def test_missing_scores_are_counted_and_unrelated_learner_cannot_inspect(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "missing.sqlite", monkeypatch)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_kind=NULL,score_value=NULL WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    select_deep(db, [1], learner=LEARNER, per_game=2, total=2)
    detail = show_selection(db, 1, LEARNER)
    assert detail["coverage"]["missing_scores"] == 1
    assert detail["coverage"]["reason_counts"]["score_unavailable"] == 1
    with pytest.raises(ValueError, match="selection is unavailable"):
        show_selection(db, 1, OPPONENT)


@pytest.mark.parametrize(
    "wdl", [None, [], [0, 0, 0], [-1, 1, 1], ["1", 2, 3], [True, 2, 3], [1000000001, 2, 3]]
)
def test_invalid_wdl_is_never_used_as_a_score_gap(wdl):
    from chess_coach.deep_selection_wdl import wdl_gap

    assert not wdl_gap(wdl, [100, 200, 700], 0.1)
    assert not wdl_gap([700, 200, 100], wdl, 0.1)


def test_unsupported_cheap_settings_are_not_selected(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "unsupported.sqlite", monkeypatch)
    row = db.connection.execute("SELECT id,config_json FROM analysis_runs").fetchone()
    config = json.loads(row["config_json"])
    config["limits_apply_per_search"] = False
    db.connection.execute(
        "UPDATE analysis_runs SET config_json=? WHERE id=?", (json.dumps(config), row["id"])
    )
    db.connection.commit()
    result = select_deep(db, [1], learner=LEARNER)
    assert result["games"][0]["status"] == "unavailable"
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 0


def test_exhausted_invocation_budget_keeps_coverage_for_later_games(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "budget.sqlite", monkeypatch, count=3)
    report = select_deep(db, [3, 1, 2], learner=LEARNER, per_game=1, total=1)
    assert report["selected"] == 1
    assert sorted(item["coverage"]["selected"] for item in report["games"]) == [0, 0, 1]
    for item in report["games"]:
        if item["coverage"]["selected"] == 0:
            assert item["coverage"]["eligible"] == 6
            assert item["coverage"]["omitted_critical"] > 0
            assert show_selection(db, item["game_id"], LEARNER)["items"] == []


def test_unattributed_game_never_creates_selection(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "unattributed.sqlite", monkeypatch)
    report = select_deep(db, [1], learner="fixture_unrelated")
    assert report["selected"] == 0 and report["games"][0]["status"] == "unavailable"
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 0
