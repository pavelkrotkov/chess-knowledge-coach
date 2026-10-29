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


def add(db, game_id, ply, outcome, *, subject="learner", version="1.0.1"):
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
                "observation_at": f"2026-10-{game_id:02}T12:00:00+00:00",
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
    ingest_pgn(db, game(1))
    ingest_pgn(db, game(2, "1. d4 d5 2. Nf3 Nf6"))
    add(db, 1, 1, "ambiguous")
    add(db, 2, 1, "success")
    boundary = "2026-10-02T12:00:00+00:00"
    result = report(db, "learner", boundary, END, START)
    assert result["previous"][0]["ambiguous"] == 1
    assert result["current"][0]["successes"] == 1
    assert result["current"][0]["strata"]
    assert result["coverage"]["analysis_stages"] == {"not analyzed": 2}
    assert sum(sum(row["rows"].values()) for row in result["recorded_mappings"]) == 2
