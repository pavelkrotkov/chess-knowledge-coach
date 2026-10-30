"""Back-rank claims require legal proof and never qualify for mastery."""

import pytest

from chess_coach.back_rank_auto import process_decision
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.mastery import update_mastery
from chess_coach.mate_auto import process_decision as process_mate
from tests.test_mate_proof import owned_game

DEFENSE = "r5k1/8/8/8/2N5/8/5PPP/6K1 w - - 0 1"
ATTACK = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"


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
