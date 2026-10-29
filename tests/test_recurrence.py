"""Behavioral checks for bounded source-linked recurrence summaries."""

import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.recurrence_report import report
from chess_coach.web import create_app

START = "2026-10-01T00:00:00+00:00"
END = "2026-11-01T00:00:00+00:00"
PREV = "2026-09-01T00:00:00+00:00"


def game(day, moves="1. e4 e5 2. Nf3 Nc6 3. Bc4"):
    return f"""[Event "Synthetic"]
[White "Learner"]
[Black "Opponent"]
[UTCDate "2026.10.{day:02}"]
[UTCTime "12:00:00"]
[TimeControl "600+0"]
[WhiteElo "1500"]
[BlackElo "1600"]
[Result "*"]

{moves} *"""


def add(db, game_id, ply, outcome, *, subject="learner", version="1.0.1", observed=None):
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=?", (game_id, ply)
    ).fetchone()[0]
    fact = record_fact_run(
        db,
        position_id=position,
        producer="fork-opportunity",
        detector_version=version,
        input_data={"synthetic": True},
        facts=[{"fact_type": "fork_opportunity", "payload": {"kind": "fork", "outcome": outcome}}],
    )
    db.connection.execute("BEGIN IMMEDIATE")
    mapping = record_mapping_run_in_transaction(
        db,
        position_id=position,
        producer="fork-opportunity-mapper",
        mapper_version=version,
        subject=subject,
        operation="execute",
        scope_key="fork-v1",
        input_data={},
        mappings=[
            {
                "skill": "fork",
                "outcome": outcome,
                "confidence": 0.5,
                "fact_ids": fact["fact_ids"],
                "context": {},
                "observation_at": observed or f"2026-10-{game_id:02}T12:00:00+00:00",
            }
        ],
    )
    db.connection.commit()
    return mapping["evidence_ids"][0]


def test_recurrence_review_boundaries_and_independence(tmp_path):
    path = tmp_path / "data.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, game(1))
    first = add(db, 1, 1, "failure")
    add(db, 1, 3, "failure")
    current = report(db, "learner", START, END, PREV)
    group = current["current"][0]
    assert (group["misses"], group["miss_games"], group["games_with_repetitions"]) == (2, 1, 1)
    assert group["currentness"] == {"currentness unverified": 2}
    ingest_pgn(db, game(2, "1. d4 d5 2. Nf3 Nf6"))
    second = add(db, 2, 1, "failure")
    review_evidence(db, second, decision="accept", actor="synthetic")
    group = report(db, "learner", START, END, PREV)["current"][0]
    assert (group["misses"], group["miss_games"]) == (3, 2)
    assert group["review"] == {"unreviewed": 2, "accepted": 1}
    review_evidence(db, second, decision="revoke", actor="synthetic")
    group = report(db, "learner", START, END, PREV)["current"][0]
    assert group["miss_games"] == 1
    review_evidence(db, first, decision="reject", actor="synthetic")
    assert report(db, "learner", START, END, PREV)["current"][0]["misses"] == 1
    assert report(db, "other", START, END, PREV)["current"] == []
    with pytest.raises(ValueError):
        report(db, "learner", END, START, PREV)
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="synthetic",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/recurrence", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "login"}
    )
    assert response.status_code == 200
    assert b"provisional recorded candidates" in response.data
    assert b"/evidence/" in response.data and b"game 1, ply 3" in response.data


def test_material_marker_matches_original_and_stale_sources_are_excluded(tmp_path, monkeypatch):
    from chess_coach.material_detector import process_decision
    from chess_coach.material_source_marker import source_marker
    from chess_coach.recurrence_marker import game_parts, marker
    from tests.test_material_pipeline import LEARNER, make_game

    db = make_game(tmp_path / "material.sqlite", monkeypatch)
    created = process_decision(db, 1, LEARNER)
    row = {"position_id": 1, "game_id": 1, "subject": LEARNER}
    assert marker(db, row, game_parts(db, 1)) == source_marker(db, 1, 1, LEARNER)
    start, end, previous = (
        "2026-01-01T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
    )
    current = report(db, LEARNER, start, end, previous)
    assert current["current"][0]["misses"] == 1
    assert current["current"][0]["currentness"] == {"marker matches": 1}
    review_evidence(db, created["evidence_ids"][0], decision="accept", actor="synthetic")
    assert report(db, LEARNER, start, end, previous)["current"][0]["review"] == {"accepted": 1}
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    changed = report(db, LEARNER, start, end, previous)
    assert changed["current"] == [] and changed["coverage"]["excluded"]["stale"] == 1


def test_comparison_boundaries_and_ambiguous_counts(tmp_path):
    db = Database(tmp_path / "windows.sqlite")
    db.initialize()
    ingest_pgn(db, game(1, "1. e4 {[%clk 0:00:20]} e5 2. Nf3"))
    ingest_pgn(db, game(2, "1. d4 d5 2. Nf3 Nf6"))
    add(db, 1, 3, "ambiguous")
    add(db, 2, 1, "success")
    boundary = "2026-10-02T12:00:00+00:00"
    result = report(db, "learner", boundary, END, START)
    assert result["previous"][0]["ambiguous"] == 1
    assert any(
        row["field"] == "clock" and row["value"] == "30 seconds or less"
        for row in result["previous"][0]["strata"]
    )
    assert result["current"][0]["successes"] == 1
    assert result["current"][0]["strata"]
    assert result["coverage"]["analysis_stages"] == {"not analyzed": 2}
    assert sum(sum(row["rows"].values()) for row in result["recorded_mappings"]) == 2


def test_back_rank_defense_operation_uses_its_recorded_outcome(tmp_path, monkeypatch):
    import sys

    from chess_coach.back_rank_auto import process_decision
    from chess_coach.mate_auto import process_decision as process_mate
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_back_rank import DEFENSE
    from tests.test_mate_proof import owned_game

    db = owned_game(tmp_path / "backrank.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    pgn = pgn.replace("[Result", '[UTCDate "2026.01.01"]\n[UTCTime "12:00:00"]\n[Result')
    db.connection.execute("UPDATE games SET pgn=? WHERE id=1", (pgn,))
    db.connection.commit()
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    result = report(
        db,
        "fixture_a",
        "2026-01-01T00:00:00+00:00",
        "2027-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00+00:00",
    )
    defense = next(item for item in result["current"] if item["skill"] == "back_rank")
    assert defense["operation"] == "prevent" and defense["successes"] == 1
    assert defense["currentness"] == {"currentness unverified": 1}


def test_cursor_reaches_beyond_300_same_timestamp_and_binds_scope(tmp_path):
    db = Database(tmp_path / "many.sqlite")
    db.initialize()
    for n in range(301):
        text = game(1, "1. e4").replace("Opponent", f"Opponent{n}")
        ingest_pgn(db, text)
        add(db, n + 1, 1, "failure", observed="2026-10-01T12:00:00+00:00")
    kwargs = {"skill": "fork", "operation": "execute"}
    first = report(db, "learner", START, END, PREV, **kwargs)
    assert first["coverage"]["evidence_limits_reached"] == ["fork.execute"]
    cursor, count, pages = first["navigation"]["next"], first["current"][0]["opportunities"], 1
    second = report(db, "learner", START, END, PREV, cursor=cursor, **kwargs)
    back = report(
        db, "learner", START, END, PREV, cursor=second["navigation"]["previous"], **kwargs
    )
    assert back["current"][0]["opportunities"] == count
    with pytest.raises(ValueError, match="cursor"):
        report(db, "other", START, END, PREV, cursor=cursor, **kwargs)
    with pytest.raises(ValueError, match="cursor"):
        report(db, "learner", "2026-10-02T00:00:00+00:00", END, PREV, cursor=cursor, **kwargs)
    while cursor:
        page = report(db, "learner", START, END, PREV, cursor=cursor, **kwargs)
        count += sum(group["opportunities"] for group in page["current"])
        cursor = page["navigation"]["next"]
        pages += 1
    assert (count, pages) == (301, 16)


def test_duplicate_import_alias_and_replay_count_once(tmp_path):
    db = Database(tmp_path / "aliases.sqlite")
    db.initialize()
    pgn = game(1, "1. e4 e5")
    ingest_pgn(db, pgn, source="fixture-a")
    ingest_pgn(db, pgn, source="fixture-b")
    first = add(db, 1, 1, "failure")
    assert add(db, 1, 1, "failure") == first
    add(db, 2, 1, "failure", observed="2026-10-01T12:00:00+00:00")
    result = report(db, "learner", START, END, PREV)
    assert result["current"][0]["opportunities"] == 1
    assert result["current"][0]["independent_games"] == 1
    assert result["coverage"]["excluded"]["duplicate decision"] == 1


def test_mapper_version_and_scope_are_enforced(tmp_path, monkeypatch):
    from chess_coach.material_detector import process_decision
    from tests.test_material_pipeline import LEARNER, make_game

    db = make_game(tmp_path / "mapper.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    window = ("2026-01-01T00:00:00+00:00", "2026-02-01T00:00:00+00:00", "2025-12-01T00:00:00+00:00")
    assert report(db, LEARNER, *window)["current"]
    run = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence_id,)
    ).fetchone()[0]
    db.connection.execute("UPDATE mapping_runs SET scope_key=? WHERE id=?", ("wrong-scope", run))
    db.connection.commit()
    assert not report(db, LEARNER, *window)["current"]
    db.connection.execute(
        "UPDATE mapping_runs SET scope_key=?, mapper_version=? WHERE id=?",
        ("material-v1", "99.0.0", run),
    )
    db.connection.execute(
        "UPDATE evidence_mappings SET mapper_version=? WHERE id=?", ("99.0.0", evidence_id)
    )
    db.connection.commit()
    assert not report(db, LEARNER, *window)["current"]


def test_report_uses_consistent_snapshot_and_preserves_caller_transaction(tmp_path, monkeypatch):
    import sqlite3

    import chess_coach.recurrence_report as module

    path = tmp_path / "race.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute("PRAGMA journal_mode=WAL")
    ingest_pgn(db, game(1))
    add(db, 1, 1, "failure")
    writer = sqlite3.connect(path)
    original = module.games
    changed = False

    def change_after_read(database, learner):
        nonlocal changed
        result = original(database, learner)
        if not changed:
            writer.execute("UPDATE mapping_runs SET status=?", ("superseded",))
            writer.commit()
            changed = True
        return result

    monkeypatch.setattr(module, "games", change_after_read)
    assert module.report(db, "learner", START, END, PREV)["current"][0]["misses"] == 1
    assert module.report(db, "learner", START, END, PREV)["current"] == []
    assert not db.connection.in_transaction
    db.connection.execute("BEGIN")
    db.connection.execute("UPDATE games SET event=? WHERE id=1", ("uncommitted",))
    module.report(db, "learner", START, END, PREV)
    assert db.connection.in_transaction
    db.connection.rollback()
    assert (
        db.connection.execute("SELECT event FROM games WHERE id=1").fetchone()[0] != "uncommitted"
    )
    writer.close()
