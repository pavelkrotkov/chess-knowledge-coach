"""Automatic observations retain bounded proof, ownership, and durable practice."""

import chess
import pytest

from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.mastery_sources import evidence_rows
from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.mate_observation import observe
from chess_coach.mate_practice import VERSION, list_candidates
from chess_coach.mate_worker import process_mates
from chess_coach.material_mastery_policy import mastery_allowed
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.unified_session_events import reveal, show, submit
from chess_coach.unified_sessions import start
from tests.test_mate_proof import BLACK_FEN, FEN, owned_game


def test_automatic_miss_replay_mastery_and_owned_practice(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "mate.sqlite", monkeypatch)
    result = process_decision(db, 1, "fixture_a")
    assert not result["replayed"]
    assert process_decision(db, 1, "fixture_a")["replayed"]
    row = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()
    evidence_id = row[0]
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["mate_source_currentness"] == "current"
    assert evidence["context"]["observation"]["immediate_mate_not_played"]
    review_evidence(db, evidence_id, decision="accept", actor="reviewer")
    row = evidence_rows(db, "fixture_a", "mate_in_one", "execute")[0]
    assert not mastery_allowed(db, row)
    from chess_coach.mastery import update_mastery

    mastery = update_mastery(db, skill="mate_in_one", operation="execute", subject="fixture_a")
    assert mastery["status"] == "insufficient"
    assert mastery["exclusions"]["mate_family_unvalidated"] == 1
    candidates = list_candidates(db, "fixture_a")["candidates"]
    assert candidates == [{"key": str(evidence_id), "review_status": "accepted"}]
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_b",
            source_type="own-game",
            version=VERSION,
            key=str(evidence_id),
        )
    state = start(
        db,
        attempt_id="attempt",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    assert "lines" not in state and "source_key" not in state
    answer = reveal(db, "attempt", "fixture_a", event_id="reveal-1")
    assert answer["hints_used"] == 1 and answer["revealed_line"]
    assert reveal(db, "attempt", "fixture_a", event_id="reveal-1") == answer
    assert show(db, "attempt", "fixture_a")["hints_used"] == 1
    move = answer["revealed_line"].split()[0]
    finished = submit(db, "attempt", "fixture_a", event_id="move-1", move=move)
    assert finished["status"] in {"active", "objective_verified"}
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["mate_source_currentness"] == "stale"
    with pytest.raises(ValueError):
        show(db, "attempt", "fixture_a")


def test_prefilter_is_unknown_and_equivalent_mates_are_not_false_failures():
    ordinary = chess.Board()
    result = observe(ordinary, ordinary.parse_uci("e2e4"), short_candidate=False)
    assert result["status"] == "unknown" and result["proof"] is None
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    result = observe(board, board.parse_uci("f7e8"), short_candidate=False)
    assert result["outcome"] == "success" and len(result["immediate_mates"]) == 4
    assert not result["immediate_mate_not_played"]
    black = chess.Board(BLACK_FEN)
    assert observe(black, black.parse_uci("g3g2"), short_candidate=False)["outcome"] == "success"


def test_worker_bounds_and_unknown_result(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "worker.sqlite", monkeypatch, fen=FEN, move="Qg1")
    config = PipelineConfig(learner="fixture_a", mate_max_scan=1, mate_max_decisions=1)
    result = process_mates(db, config)
    assert result["processed"] == 1 and result["limits"]["nodes_per_decision"] == 6000
    assert process_mates(db, config)["replayed"] == 1


def test_short_mate_proof_lines_cover_every_defense_and_skipped_is_unknown():
    from chess_coach.mate_practice_lines import prepared_lines

    board = chess.Board("5r1k/6pp/8/3QN3/8/1B6/8/K7 w - - 0 1")
    played = board.parse_uci("d5g8")
    result = observe(board, played, short_candidate=True)
    assert result["outcome"] == "success"
    root = next(root for root in result["proof"]["alternatives"] if root["move"]["uci"] == "d5g8")
    assert root["distance_plies"] == 3
    assert "d5g8 f8g8 e5f7" in prepared_lines(board, result["proof"])


def test_private_browser_shows_automatic_provisional_evidence(tmp_path, monkeypatch):
    from chess_coach.web import create_app

    path = tmp_path / "browser.sqlite"
    db = owned_game(path, monkeypatch)
    process_decision(db, 1, "fixture_a")
    evidence_id = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="reviewer",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get(f"/evidence/{evidence_id}", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"immediate mate was available" in page.data
    assert b"no ability or cause inferred" in page.data
    page = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert b"Own-game mate practice" in page.data and b"Practice mate" in page.data
    page = client.get("/decisions/1/mate", base_url="https://coach.invalid", headers=headers)
    assert b"Automatic bounded observation: opportunity" in page.data


def test_game_mate_policy_rejects_foreign_and_mismatched_lineage(monkeypatch):
    from chess_coach import mate_mastery_policy as policy
    from chess_coach.tactical_rules import mate_in_one_fact

    row = {
        "id": 1,
        "skill": "mate_in_one",
        "operation": "execute",
        "outcome": "success",
        "mapping_producer": "mate-in-one-mapper",
        "mapper_version": "mate-one-1.0.0",
        "run_mapper_version": "mate-one-1.0.0",
        "link_count": 1,
    }
    fact = {
        "producer": "mate-in-one",
        "fact_type": "mate_in_one",
        "detector_version": "1.0.0",
        "run_detector_version": "1.0.0",
        "detector_status": "active",
        "payload": mate_in_one_fact(FEN, "g6g7"),
    }
    monkeypatch.setattr(policy, "facts_for_evidence", lambda *_: [fact])
    monkeypatch.setattr(policy, "matches_game", lambda *_: True)
    assert policy.mastery_allowed(None, row)
    assert not policy.mastery_allowed(None, {**row, "skill": "calculation"})
    assert not policy.mastery_allowed(None, {**row, "mapping_producer": "foreign"})
    assert not policy.mastery_allowed(None, {**row, "run_mapper_version": "other"})
    assert not policy.mastery_allowed(None, {**row, "link_count": 0})
    for field in ("producer", "fact_type", "detector_version", "run_detector_version"):
        changed = {**fact, field: "foreign"}
        monkeypatch.setattr(policy, "facts_for_evidence", lambda *_, value=changed: [value])
        assert not policy.mastery_allowed(None, row)
    renamed = {
        **fact,
        "producer": "foreign",
        "fact_type": "foreign",
        "detector_version": "foreign",
        "run_detector_version": "foreign",
    }
    monkeypatch.setattr(policy, "facts_for_evidence", lambda *_: [renamed])
    assert not policy.mastery_allowed(None, {**row, "mapping_producer": "foreign"})
    monkeypatch.setattr(policy, "facts_for_evidence", lambda *_: [])
    assert not policy.mastery_allowed(None, row)


def test_corrupted_cached_fact_cannot_replay_or_offer_practice(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "corrupt.sqlite", monkeypatch)
    process_decision(db, 1, "fixture_a")
    db.connection.execute(
        "UPDATE detector_facts SET payload_json='{}' WHERE fact_type='bounded_mate'"
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="stored mate output"):
        process_decision(db, 1, "fixture_a")
    assert not list_candidates(db, "fixture_a")["candidates"]


def test_pipeline_backfills_mates_without_automatic_review(tmp_path, monkeypatch):
    import sys

    import httpx

    from chess_coach.pipeline import process_pipeline

    db = owned_game(tmp_path / "pipeline.sqlite", monkeypatch)
    config = PipelineConfig(
        learner="fixture_a",
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        material_enabled=False,
        mate_max_decisions=1,
    )
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=network)
    assert "forks" in result and result["mate"]["processed"] == 1
    assert result["mate"]["outcomes"] == {"opportunity": 1}
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    assert process_pipeline(db, config, transport=network)["mate"]["replayed"] == 1


def test_changed_and_reactivated_source_preserves_review_and_lineage(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "reactivated.sqlite", monkeypatch)
    first = process_decision(db, 1, "fixture_a")
    evidence_id = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    review_evidence(db, evidence_id, decision="accept", actor="reviewer")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    second = process_decision(db, 1, "fixture_a")
    assert second["run_id"] != first["run_id"]
    assert inspect_evidence(db, evidence_id)["lifecycle_status"] == "superseded"
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    restored = process_decision(db, 1, "fixture_a")
    assert restored["run_id"] not in {first["run_id"], second["run_id"]}
    assert process_decision(db, 1, "fixture_a")["run_id"] == restored["run_id"]
    assert inspect_evidence(db, evidence_id)["review_status"] == "accepted"
    current = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=? AND r.status='active'",
        (MAPPER,),
    ).fetchone()[0]
    assert inspect_evidence(db, current)["review_status"] == "unreviewed"


def test_source_change_during_proof_never_publishes(tmp_path, monkeypatch):
    import chess_coach.mate_auto as automatic

    db = owned_game(tmp_path / "changed.sqlite", monkeypatch)
    original = automatic.observe

    def change_source(*args, **kwargs):
        fact = original(*args, **kwargs)
        db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
        db.connection.commit()
        return fact

    monkeypatch.setattr(automatic, "observe", change_source)
    with pytest.raises(ValueError, match="mate source changed"):
        process_decision(db, 1, "fixture_a")
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_facts WHERE fact_type='bounded_mate'"
        ).fetchone()[0]
        == 0
    )


def test_legacy_mate_fact_must_match_the_original_decision(tmp_path, monkeypatch):
    from chess_coach.mate_legacy_mastery import matches_game
    from chess_coach.tactical_rules import mate_in_one_fact

    db = owned_game(tmp_path / "legacy.sqlite", monkeypatch, move="Qg7#")
    good = {"payload": mate_in_one_fact(FEN, "g6g7")}
    other = {"payload": mate_in_one_fact(FEN, "g6g1")}
    assert matches_game(db, {"position_id": 1}, good)
    assert not matches_game(db, {"position_id": 1}, other)


def test_mate_browser_reveal_uses_accessible_board_and_counts_assistance(tmp_path, monkeypatch):
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "accessible-mate.sqlite"
    db = owned_game(path, monkeypatch)
    process_decision(db, 1, "fixture_a")
    key = list_candidates(db, "fixture_a")["candidates"][0]["key"]
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="reviewer",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    origin = "https://coach.invalid"
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url=origin, headers=headers)
    csrf = token(library, "csrf")
    response = client.post(
        "/unified/start",
        base_url=origin,
        headers=headers | {"Origin": origin},
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": key},
    )
    assert response.status_code == 303
    page = client.get(response.headers["Location"], base_url=origin, headers=headers)
    assert b"data-move-board" in page.data and b"View source evidence" not in page.data
    assert b"g6g7" not in page.data and b"Qg7#" not in page.data
    values = {"csrf": csrf, "attempt": token(page, "attempt"), "event": token(page, "event")}
    for _ in range(2):
        revealed = client.post(
            "/unified/reveal", base_url=origin, headers=headers | {"Origin": origin}, data=values
        )
        assert revealed.status_code == 200 and b"One supplied continuation" in revealed.data
    row = db.connection.execute(
        "SELECT hints_used FROM unified_sessions WHERE attempt_id=?", (values["attempt"],)
    ).fetchone()
    assert row[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
