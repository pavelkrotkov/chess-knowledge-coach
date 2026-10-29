"""Real local proof reuse retains currentness and bounded preview behavior."""

import json
import shutil
import sys
from time import perf_counter

import chess
import pytest

from chess_coach import pawn_proof, pawn_proof_cache, pawn_tables
from chess_coach.decision_history import decision_board
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.pawn_coach_detector import process_decision
from chess_coach.pawn_coach_observation import observe
from chess_coach.pawn_practice import VERSION
from chess_coach.pawn_practice_list import list_candidates
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_session_events import show
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

POSITIONS = (
    ("8/8/8/8/2k5/4K3/3P4/8 w - - 0 1", "d2d4"),
    ("8/3p4/4k3/2K5/8/8/8/8 b - - 0 1", "d7d5"),
    ("8/1K6/P7/1k6/8/8/8/8 w - - 0 1", "b7a8"),
    ("8/8/8/8/1K6/p7/1k6/8 b - - 0 1", "b2a1"),
)


def games(tmp_path, monkeypatch, count=4):
    first, move = POSITIONS[0]
    db = owned_game(
        tmp_path / "reuse.sqlite",
        monkeypatch,
        fen=first,
        move=chess.Board(first).san(chess.Move.from_uci(move)),
    )
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    for index, (fen, move) in enumerate(POSITIONS[1:count], 2):
        board = chess.Board(fen)
        white, black = ("fixture_a", "fixture_b") if board.turn else ("fixture_b", "fixture_a")
        pgn = f'[Event "Synthetic {index}"]\n[White "{white}"]\n[Black "{black}"]\n[SetUp "1"]\n[FEN "{fen}"]\n[Result "*"]\n\n1. {board.san(chess.Move.from_uci(move))} *\n'
        assert ingest_pgn(db, pgn)["games"] == 1
        game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
        assert (
            run_analysis(
                db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
    rows = db.connection.execute("SELECT id FROM positions ORDER BY id").fetchall()
    for row in rows:
        assert process_decision(db, row["id"], "fixture_a")["outcome"] == "failure"
    return db


def clear_cache():
    with pawn_proof_cache._lock:
        pawn_proof_cache._reports.clear()


def begin(db, key, attempt):
    return start(
        db,
        attempt_id=attempt,
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=key,
    )


def test_four_distinct_sources_cold_warm_pages_and_session(tmp_path, monkeypatch):
    db = games(tmp_path, monkeypatch)
    positions = db.connection.execute("SELECT * FROM positions ORDER BY id").fetchall()
    uncached = [pawn_proof.inspect(decision_board(db, row)) for row in positions]
    assert len({row[0] for row in POSITIONS}) == 4
    learning_tables = (
        "evidence_mappings",
        "mastery_events",
        "mastery_states",
        "training_items",
        "training_attempts",
    )
    before_learning = {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in learning_tables
    }
    clear_cache()
    calls = []
    original = pawn_proof.report

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(pawn_proof, "report", counted)
    before = None
    seen = []
    timings = []
    for index in range(4):
        t = perf_counter()
        page = list_candidates(db, "fixture_a", before=before)
        cold = perf_counter() - t
        assert page["scanned"] == 1 and len(calls) == index
        assert "objective" not in page["candidates"][0]
        key = page["candidates"][0]["key"]
        seen.append(key)
        t = perf_counter()
        assert list_candidates(db, "fixture_a", before=before) == page
        assert len(calls) == index
        warm = perf_counter() - t
        t = perf_counter()
        begin(db, key, f"attempt-{index}")
        started = perf_counter() - t
        t = perf_counter()
        show(db, f"attempt-{index}", "fixture_a")
        reopened = perf_counter() - t
        assert len(calls) == index + 1
        timings.append((cold, warm, started, reopened))
        before = page["next_before"]
    assert before is None and len(set(seen)) == 4
    for row, expected in zip(positions, uncached, strict=True):
        board = decision_board(db, row)
        cached = pawn_proof.inspect_reused(board)
        assert cached == expected and observe(cached, row["uci"]) == observe(expected, row["uci"])
        cached["alternatives"].clear()
        assert pawn_proof.inspect_reused(board) == expected
    assert len(calls) == 4
    app = create_app(
        db_path=db.path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    t = perf_counter()
    response = client.get("/library", base_url="https://coach.invalid", headers=headers)
    http_warm = perf_counter() - t
    assert response.status_code == 200 and b"Next pawn source" in response.data
    assert b"Verify and start pawn exercise" in response.data
    assert b"not yet verified for practice" in response.data
    assert b"preserving a win" not in response.data
    cursor = None
    for key in seen:
        url = "/library" + (f"?pawn_before={cursor}" if cursor else "")
        displayed = client.get(url, base_url="https://coach.invalid", headers=headers)
        assert (
            displayed.status_code == 200
            and ("value=" + chr(34) + key + chr(34)).encode() in displayed.data
        )
        cursor = list_candidates(db, "fixture_a", before=cursor)["next_before"]
        if cursor:
            assert f"pawn_before={cursor}".encode() in displayed.data
    assert cursor is None
    assert {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in learning_tables
    } == before_learning
    assert (
        client.get(
            "/library?pawn_before=bad", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 400
    )
    print(
        "synthetic page cold/warm/start/reopen seconds:",
        [[round(x, 3) for x in row] for row in timings],
    )
    print(
        "synthetic warm library HTTP seconds:", round(http_warm, 3), "full proof calls:", len(calls)
    )
    db.close()


def test_cached_session_rechecks_sources_resources_review_and_subject(tmp_path, monkeypatch):
    db = games(tmp_path, monkeypatch, count=1)
    clear_cache()
    item = list_candidates(db, "fixture_a")["candidates"][0]
    key = item["key"]
    begin(db, key, "owned")
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_b")
    assert not list_candidates(db, "fixture_b")["candidates"]
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_b",
            source_type="own-game",
            version=VERSION,
            key=key,
        )
    resource_dir = tmp_path / "resource-copy"
    shutil.copytree(pawn_tables.DIRECTORY, resource_dir)
    monkeypatch.setattr(
        pawn_proof, "open_verified", lambda: pawn_tables.open_verified(resource_dir)
    )
    manifest = json.loads((resource_dir / "manifest.json").read_text())
    file = resource_dir / next(iter(manifest))
    original = file.read_bytes()
    file.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    assert not list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_a")
    file.write_bytes(original)
    assert list_candidates(db, "fixture_a")["candidates"] and show(db, "owned", "fixture_a")
    fact = db.connection.execute(
        "SELECT id,payload_json FROM detector_facts WHERE fact_type='pawn_endgame_opportunity'"
    ).fetchone()
    assert fact is not None
    payload = json.loads(fact["payload_json"])
    payload["outcome"] = "success"
    db.connection.execute(
        "UPDATE detector_facts SET payload_json=? WHERE id=?", (json.dumps(payload), fact["id"])
    )
    db.connection.commit()
    assert not list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_a")
    db.connection.execute(
        "UPDATE detector_facts SET payload_json=? WHERE id=?", (fact["payload_json"], fact["id"])
    )
    db.connection.commit()
    assert show(db, "owned", "fixture_a")
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.pawn_inspection.VERSION", "changed-proof")
        patch.setattr(pawn_proof, "VERSION", "changed-proof")
        assert not list_candidates(db, "fixture_a")["candidates"]
        with pytest.raises(ValueError):
            show(db, "owned", "fixture_a")
    assert show(db, "owned", "fixture_a")
    with monkeypatch.context() as patch:
        patch.setattr(pawn_tables, "MANIFEST_SHA256", "invalid")
        assert not list_candidates(db, "fixture_a")["candidates"]
        with pytest.raises(ValueError):
            show(db, "owned", "fixture_a")
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    assert not list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_a")
    db.connection.execute("UPDATE pipeline_stages SET status='complete' WHERE stage='analysis'")
    db.connection.commit()
    assert show(db, "owned", "fixture_a")
    review_evidence(db, int(key), decision="accept", actor="fixture_reviewer")
    review_evidence(db, int(key), decision="revoke", actor="fixture_reviewer")
    assert not list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_a")
    review_evidence(db, int(key), decision="accept", actor="fixture_reviewer")
    assert list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "owned", "fixture_a")
    begin(db, key, "new-after-review")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=? AND role=?",
        (1, "best"),
    )
    db.connection.commit()
    assert not list_candidates(db, "fixture_a")["candidates"]
    with pytest.raises(ValueError):
        show(db, "new-after-review", "fixture_a")
    changed = process_decision(db, 1, "fixture_a")["evidence_ids"][0]
    assert changed != int(key)
    assert list_candidates(db, "fixture_a")["candidates"][0]["review_status"] == "unreviewed"
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=? AND role=?",
        (1, "best"),
    )
    db.connection.commit()
    reactivated = process_decision(db, 1, "fixture_a")["evidence_ids"][0]
    assert reactivated not in {changed, int(key)}
    assert list_candidates(db, "fixture_a")["candidates"][0]["review_status"] == "unreviewed"
    with pytest.raises(ValueError):
        show(db, "new-after-review", "fixture_a")
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0
    db.close()


def test_scope_and_history_are_checked_before_cached_proof(monkeypatch):
    board = chess.Board(POSITIONS[0][0])
    pawn_proof.inspect_reused(board)

    class NonstandardBoard(chess.Board):
        pass

    def unavailable():
        raise AssertionError("resource verification must follow scope and history checks")

    monkeypatch.setattr(pawn_proof, "open_verified", unavailable)
    assert pawn_proof.inspect_reused(NonstandardBoard(board.fen()))["status"] == "unsupported"
    unknown = chess.Board(board.fen().replace(" 0 1", " 1 1"))
    result = pawn_proof.inspect_reused(unknown)
    assert result == {"status": "unknown", "reason": "incomplete_repetition_history"}


def test_key_distinguishes_same_fen_with_different_histories_and_cache_is_bounded():
    fen = "7k/8/8/8/8/8/P7/K7 w - - 0 1"
    first, second = chess.Board(fen), chess.Board(fen)
    for move in ("a1b1", "h8g8", "b1a1", "g8h8"):
        first.push_uci(move)
    for move in ("a1b2", "h8h7", "b2a1", "h7h8"):
        second.push_uci(move)
    assert first.fen() == second.fen()
    assert pawn_proof_cache.key(first, "v", "m", 6000, 5) != pawn_proof_cache.key(
        second, "v", "m", 6000, 5
    )
    clear_cache()
    for i in range(33):
        pawn_proof_cache.put((i,), {"result": i})
    assert pawn_proof_cache.get((0,)) is None
    assert pawn_proof_cache.get((32,)) == {"result": 32}
    assert len(pawn_proof_cache._reports) == 32
    clear_cache()


def test_coherent_forged_record_is_only_a_reference_and_cannot_start(tmp_path, monkeypatch):
    from chess_coach.fact_fingerprint import canonical, digest

    db = games(tmp_path, monkeypatch, count=1)
    evidence = db.connection.execute(
        "SELECT id,context_json,mapping_run_id FROM evidence_mappings"
    ).fetchone()
    fact = db.connection.execute("SELECT id,run_id,payload_json FROM detector_facts").fetchone()
    detector = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["run_id"],)
    ).fetchone()
    mapping = db.connection.execute(
        "SELECT input_json FROM mapping_runs WHERE id=?", (evidence["mapping_run_id"],)
    ).fetchone()
    payload = json.loads(fact["payload_json"])
    payload["proof"]["nodes"] += 1
    inputs = json.loads(detector["input_json"])
    inputs["detector_input"]["proof_digest"] = digest(canonical(payload["proof"]))
    context = json.loads(evidence["context_json"])
    context["pawn_observation"] = payload
    mapping_input = json.loads(mapping["input_json"])
    mapping_input["source"] = inputs["detector_input"]
    mapping_input["context"] = context
    db.connection.execute(
        "UPDATE detector_facts SET payload_json=? WHERE id=?", (json.dumps(payload), fact["id"])
    )
    db.connection.execute(
        "UPDATE detector_runs SET input_json=? WHERE id=?", (json.dumps(inputs), fact["run_id"])
    )
    db.connection.execute(
        "UPDATE evidence_mappings SET context_json=? WHERE id=?",
        (json.dumps(context), evidence["id"]),
    )
    db.connection.execute(
        "UPDATE mapping_runs SET input_json=? WHERE id=?",
        (json.dumps(mapping_input), evidence["mapping_run_id"]),
    )
    db.connection.commit()
    clear_cache()
    calls = []
    original = pawn_proof.report

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(pawn_proof, "report", counted)
    references = list_candidates(db, "fixture_a")["candidates"]
    assert references == [
        {"key": str(evidence["id"]), "review_status": "unreviewed", "verification": "required"}
    ]
    assert calls == []
    with pytest.raises(ValueError):
        begin(db, str(evidence["id"]), "forged")
    assert len(calls) == 1
    assert db.connection.execute("SELECT COUNT(*) FROM unified_sessions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    db.close()
