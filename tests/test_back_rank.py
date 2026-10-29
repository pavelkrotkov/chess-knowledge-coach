"""Back-rank claims require legal proof and never qualify for mastery."""

import chess
import pytest

from chess_coach.back_rank_attack import prove
from chess_coach.back_rank_auto import process_decision
from chess_coach.back_rank_defense import observe
from chess_coach.back_rank_terminal import terminal
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.mastery import update_mastery
from chess_coach.mate_auto import process_decision as process_mate
from chess_coach.mate_proof import prove_short_mates
from tests.test_mate_proof import owned_game

DEFENSE = "r5k1/8/8/8/2N5/8/5PPP/6K1 w - - 0 1"
ATTACK = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"


@pytest.mark.parametrize(
    "mirrored,safe_move,unsafe_move",
    [
        (False, "g2g3", "c4d6"),
        (True, "g7g6", "c5d3"),
    ],
)
def test_anchored_threat_and_legal_luft_alternatives(mirrored, safe_move, unsafe_move):
    board = chess.Board(DEFENSE)
    if mirrored:
        board = board.mirror()
    before = board.fen()
    safe = observe(board, board.parse_uci(safe_move))
    unsafe = observe(board, board.parse_uci(unsafe_move))
    assert (safe["outcome"], safe["origin"]) == ("avoids", "anchored_preexisting")
    assert (unsafe["outcome"], unsafe["origin"]) == ("allows", "anchored_preexisting")
    assert safe["anchors"] and safe["nodes"] <= safe["node_limit"]
    assert {item["move"]["uci"] for item in safe["alternatives"]} == {
        move.uci() for move in board.legal_moves
    }
    selected = next(item for item in safe["alternatives"] if item["move"]["uci"] == safe_move)
    assert selected["status"] == "complete" and not selected["back_rank"]
    assert not selected["other_mates"] and board.fen() == before


def test_newly_allowed_line_is_not_a_preexisting_threat():
    board = chess.Board("r5k1/8/3R4/8/2b5/8/5PPP/6K1 w - - 0 1")
    result = observe(board, board.parse_uci("d6h6"))
    assert result["status"] == "opportunity"
    assert result["outcome"] == "allows"
    assert result["origin"] == "newly_allowed"


def test_avoiding_back_rank_mate_does_not_certify_another_immediate_mate():
    board = chess.Board("r5k1/q7/8/8/1N5b/8/5PPP/6K1 w - - 0 1")
    result = observe(board, board.parse_uci("g1f1"))
    played = next(item for item in result["alternatives"] if item["move"]["uci"] == "g1f1")
    assert not played["back_rank"]
    assert any(move["uci"] == "a7f2" for move in played["other_mates"])
    assert result["status"] == "unknown" and result.get("outcome") != "avoids"


def test_exhaustion_is_unknown_and_never_success():
    board = chess.Board(DEFENSE)
    result = observe(board, board.parse_uci("g2g3"), node_limit=1)
    assert result["status"] == "unknown"
    assert result["reason"] == "incomplete_alternatives"
    assert result["nodes"] <= 1


def test_attacking_mate_requires_home_rank_and_actual_checker():
    board = chess.Board(ATTACK)
    result = prove(board, prove_short_mates(board))
    root = next(item for item in result["alternatives"] if item["move"]["uci"] == "a1a8")
    assert root["status"] == "proved" and root["distance_plies"] == 1
    assert root["geometry"]["king"] == "g8"
    assert set(root["geometry"]["occupied_flights"]) == {"f7", "g7", "h7"}
    board.push_uci("a1a8")
    assert terminal(board)["checkers"] == ["a8"]
    ordinary = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    ordinary.push_uci("f7g7")
    assert ordinary.is_checkmate() and terminal(ordinary) is None


@pytest.mark.parametrize("mirrored,move", [(False, "h5f7"), (True, "h4f2")])
def test_short_attack_proves_terminal_mate_after_every_legal_defense(mirrored, move):
    board = chess.Board("6k1/5ppp/8/7Q/8/5R2/7r/K4R2 w - - 0 1")
    if mirrored:
        board = board.mirror()
    result = prove(board, prove_short_mates(board))
    root = next(item for item in result["alternatives"] if item["move"]["uci"] == move)
    assert root["status"] == "proved" and root["distance_plies"] == 3
    board.push_uci(move)
    assert {item["defense"]["uci"] for item in root["defenses"]} == {
        reply.uci() for reply in board.legal_moves
    }
    for item in root["defenses"]:
        board.push_uci(item["defense"]["uci"])
        board.push_uci(item["mate"]["move"]["uci"])
        assert terminal(board)
        board.pop()
        board.pop()


def test_short_attack_preserves_unknown_prerequisite_and_budget():
    board = chess.Board(ATTACK)
    original = prove_short_mates(board, node_limit=1)
    result = prove(board, original, node_limit=1)
    assert result["status"] == "unknown"
    assert result["nodes"] <= 1


def test_automatic_defense_is_provisional_replayable_and_closed(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "back-rank.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    result = process_decision(db, 1, "fixture_a")
    assert result["observation_status"] == "opportunity"
    assert process_decision(db, 1, "fixture_a")["replayed"]
    row = db.connection.execute(
        "SELECT id,outcome FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()
    assert row["outcome"] == "success"
    evidence = inspect_evidence(db, row["id"])
    assert evidence["review_status"] == "unreviewed"
    review_evidence(db, row["id"], decision="accept", actor="reviewer")
    mastery = update_mastery(db, skill="back_rank", operation="prevent", subject="fixture_a")
    assert mastery["status"] == "insufficient"
    assert mastery["exclusions"]["back_rank_family_unvalidated"] == 1
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    with pytest.raises(ValueError):
        process_decision(db, 1, "fixture_a")


def test_back_rank_practice_ownership_reveal_and_safe_line(tmp_path, monkeypatch):
    from chess_coach.back_rank_practice import VERSION, list_candidates
    from chess_coach.unified_session_events import reveal, show, submit
    from chess_coach.unified_sessions import start

    db = owned_game(tmp_path / "practice.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    item = list_candidates(db, "fixture_a")["candidates"][0]
    assert item["objective"] == "back_rank_defense"
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_b",
            source_type="own-game",
            version=VERSION,
            key=item["key"],
        )
    state = start(
        db,
        attempt_id="own",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=item["key"],
    )
    assert "lines" not in state and "source_key" not in state
    assert show(db, "own", "fixture_a")["status"] == "active"
    answer = reveal(db, "own", "fixture_a", event_id="reveal")
    assert answer["hints_used"] == 1
    assert reveal(db, "own", "fixture_a", event_id="reveal") == answer
    move = answer["revealed_line"].split()[0]
    done = submit(db, "own", "fixture_a", event_id="move", move=move)
    assert done["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
    db.connection.commit()
    with pytest.raises(ValueError):
        show(db, "own", "fixture_a")


def test_unlisted_defense_requires_verification_and_rejection_removes_source(tmp_path, monkeypatch):
    from chess_coach.back_rank_practice import VERSION, list_candidates
    from chess_coach.unified_session_events import submit
    from chess_coach.unified_sessions import start

    db = owned_game(tmp_path / "unlisted.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    item = list_candidates(db, "fixture_a")["candidates"][0]
    start(
        db,
        attempt_id="line",
        subject="fixture_a",
        source_type="own-game",
        version=VERSION,
        key=item["key"],
    )
    result = submit(db, "line", "fixture_a", event_id="move", move="c4d6")
    assert result["status"] == "needs_verification"
    review_evidence(db, int(item["key"]), decision="reject", actor="reviewer")
    assert not list_candidates(db, "fixture_a")["candidates"]


def test_attack_source_offers_a_verified_back_rank_mate(tmp_path, monkeypatch):
    from chess_coach.back_rank_practice import list_candidates

    db = owned_game(tmp_path / "attack.sqlite", monkeypatch, fen=ATTACK, move="Ra8#")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    item = list_candidates(db, "fixture_a")["candidates"][0]
    assert item["objective"] == "checkmate"


def test_back_rank_browser_hides_evidence_until_completion(tmp_path, monkeypatch):
    from chess_coach.back_rank_practice import VERSION, list_candidates
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db = owned_game(path, monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    item = list_candidates(db, "fixture_a")["candidates"][0]
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
    assert b"Own-game back-rank practice" in library.data
    csrf = token(library, "csrf")
    response = client.post(
        "/unified/start",
        base_url=origin,
        headers=headers | {"Origin": origin},
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": item["key"]},
    )
    page = client.get(response.headers["Location"], base_url=origin, headers=headers)
    assert b"View source evidence" not in page.data
    assert b"Avoid immediate mate" in page.data
    decision = client.get("/decisions/1/mate", base_url=origin, headers=headers)
    assert b"Back-rank observation: opportunity" in decision.data
    evidence = client.get(f"/evidence/{item['key']}", base_url=origin, headers=headers)
    assert evidence.status_code == 200
    assert b"occupied flights" in evidence.data
    assert b"no immediate checkmate found" in evidence.data
    assert b"later counterplay remain unresolved" in evidence.data


def test_closed_gate_survives_renamed_or_missing_family_provenance():
    from chess_coach.back_rank_mastery import closed

    row = {"skill": "back_rank", "mapping_producer": "other", "back_rank_fact_count": 0}
    assert closed(row)
    assert closed({**row, "skill": "foreign", "mapping_producer": "back-rank-observation-mapper"})
    assert closed({**row, "skill": "foreign", "back_rank_fact_count": 1})
    assert not closed({**row, "skill": "foreign"})


def test_back_rank_worker_is_bounded_and_replays(tmp_path, monkeypatch):
    from chess_coach.mate_worker import process_mates
    from chess_coach.pipeline_config import PipelineConfig

    db = owned_game(tmp_path / "worker.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    config = PipelineConfig(learner="fixture_a", mate_max_scan=1, mate_max_decisions=1)
    first = process_mates(db, config)
    assert first["back_rank"]["processed"] == 1
    assert first["back_rank"]["outcomes"] == {"opportunity": 1}
    assert first["back_rank"]["nodes_per_defense"] == 6000
    assert process_mates(db, config)["back_rank"]["replayed"] == 1


def test_source_change_during_back_rank_proof_never_publishes(tmp_path, monkeypatch):
    from chess_coach import back_rank_auto

    db = owned_game(tmp_path / "race.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    original = back_rank_auto._observe

    def change_source(*args):
        result = original(*args)
        db.connection.execute("UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'")
        db.connection.commit()
        return result

    monkeypatch.setattr(back_rank_auto, "_observe", change_source)
    with pytest.raises(ValueError):
        process_decision(db, 1, "fixture_a")
    count = db.connection.execute(
        "SELECT COUNT(*) FROM detector_facts WHERE fact_type='back_rank'"
    ).fetchone()[0]
    assert count == 0


def test_stalemate_is_not_a_back_rank_mate():
    board = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
    board.push_san("Qf7")
    assert board.is_stalemate()
    assert terminal(board) is None


@pytest.mark.parametrize("change", ["renamed", "missing_fact", "version_mismatch"])
def test_reviewed_family_stays_closed_after_lineage_tampering(tmp_path, monkeypatch, change):
    db = owned_game(tmp_path / "tampered.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    process_decision(db, 1, "fixture_a")
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()[0]
    review_evidence(db, evidence, decision="accept", actor="reviewer")
    if change == "renamed":
        db.connection.execute(
            "UPDATE mapping_runs SET producer='foreign' WHERE producer='back-rank-observation-mapper'"
        )
        db.connection.execute(
            "UPDATE detector_runs SET producer='foreign' WHERE producer='back-rank-observation'"
        )
        db.connection.execute(
            "UPDATE detector_facts SET fact_type='foreign' WHERE fact_type='back_rank'"
        )
    elif change == "missing_fact":
        db.connection.execute(
            "UPDATE evidence_fact_links SET active=0 WHERE evidence_id=?", (evidence,)
        )
    else:
        db.connection.execute(
            "UPDATE mapping_runs SET mapper_version='foreign' WHERE producer='back-rank-observation-mapper'"
        )
    db.connection.commit()
    mastery = update_mastery(db, skill="back_rank", operation="prevent", subject="fixture_a")
    assert mastery["status"] == "insufficient"
    assert mastery["exclusions"]["back_rank_family_unvalidated"] == 1


def test_changed_and_restored_source_preserves_accepted_history(tmp_path, monkeypatch):
    db = owned_game(tmp_path / "history.sqlite", monkeypatch, fen=DEFENSE, move="g3")
    process_mate(db, 1, "fixture_a")
    first = process_decision(db, 1, "fixture_a")
    old = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()[0]
    review_evidence(db, old, decision="accept", actor="reviewer")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    process_mate(db, 1, "fixture_a")
    second = process_decision(db, 1, "fixture_a")
    assert second["run_id"] != first["run_id"]
    previous = inspect_evidence(db, old)
    assert previous["lifecycle_status"] == "superseded" and previous["review_status"] == "accepted"
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    process_mate(db, 1, "fixture_a")
    restored = process_decision(db, 1, "fixture_a")
    assert restored["run_id"] not in {first["run_id"], second["run_id"]}
    current = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id "
        "WHERE r.producer='back-rank-observation-mapper' AND r.status='active'"
    ).fetchone()[0]
    assert inspect_evidence(db, current)["review_status"] == "unreviewed"
