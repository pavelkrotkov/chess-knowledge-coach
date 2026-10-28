"""Bounded, read-only planning over verified opportunities and due items."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import cast

import chess
import chess.pgn
import pytest

from chess_coach.curriculum import daily_plan
from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.puzzle_sessions import start_attempt
from chess_coach.tactical_opportunities import record_game_opportunities
from chess_coach.training import create_training_item, review_item
from chess_coach.training_feedback import puzzle_training_ref, submit_training_move

FEN_A = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"
FEN_B = "6k1/8/6K1/1Q6/8/8/8/8 b - - 0 1"
NOW = datetime(2026, 10, 27, 18, 0, tzinfo=UTC)


def database():
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v1','fixture','hash1')"
    )
    db.connection.commit()
    return db


def puzzle(db, puzzle_id, fen, solution, rating, *, version="v1", themes="[]"):
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES (?,(SELECT id FROM puzzle_corpora WHERE version=?),?,'',?,?,80,?,'execute')""",
        (puzzle_id, version, fen, solution, rating, themes),
    )
    db.connection.commit()


def item(db, puzzle_id, due, *, version="v1"):
    item_id = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref(version, puzzle_id),
        skill="mate_in_one",
        operation="execute",
    )
    db.connection.execute("UPDATE training_items SET due=? WHERE id=?", (due.isoformat(), item_id))
    db.connection.commit()
    return item_id


def test_due_first_then_verified_new_with_prompt_dedup_and_no_writes():
    db = database()
    puzzle(db, "fake", chess.STARTING_FEN, "e2e4 e7e5", 100, themes='["mateIn1"]')
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 1200)
    puzzle(db, "duplicate", FEN_A.replace("0 1", "17 40"), "g8h8 c5f8", 800)
    puzzle(db, "new", FEN_B, "g8h8 b5b8", 900)
    due_id = item(db, "due", NOW - timedelta(hours=1))
    before = db.connection.total_changes
    plan = daily_plan(db, subject="learner", corpus_version="v1", limit=5, as_of=NOW)
    assert db.connection.total_changes == before
    assert not db.connection.in_transaction
    assert plan["evidence"]["state"] == "cold_start"
    assert [(row["kind"], row["puzzle_id"]) for row in plan["items"]] == [
        ("due", "due"),
        ("new", "new"),
    ]
    assert plan["items"][0]["item_id"] == due_id
    assert len({row["prompt_key"] for row in plan["items"]}) == 2
    assert all(row["objective"] == "Find mate in one." for row in plan["items"])
    assert all("solution" not in row for row in plan["items"])
    assert "c5f8" not in json.dumps(plan)
    assert plan == daily_plan(db, subject=" LEARNER ", corpus_version="v1", limit=5, as_of=NOW)


def test_future_scheduled_item_is_not_selected_as_new():
    db = database()
    puzzle(db, "later", FEN_A, "g8h8 c5f8", 500)
    item(db, "later", NOW + timedelta(days=1))
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["items"] == []
    assert plan["corpus_status"] == "no_new_candidates"


def test_missing_empty_and_capped_corpus_are_distinguished():
    db = database()
    assert (
        daily_plan(db, subject="learner", corpus_version="missing", as_of=NOW)["corpus_status"]
        == "unknown_corpus"
    )
    assert (
        daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)["corpus_status"]
        == "empty_corpus"
    )
    puzzle(db, "fake", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "valid", FEN_A, "g8h8 c5f8", 200)
    capped = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, as_of=NOW)
    assert capped["items"] == [] and capped["corpus_status"] == "scan_incomplete"
    assert capped["scan"]["corpus_examined"] == 1 and capped["scan"]["corpus_incomplete"]


def test_incomplete_due_scan_never_claims_new_items_are_next():
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 200)
    puzzle(db, "new", FEN_B, "g8h8 b5b8", 300)
    item(db, "bad", NOW - timedelta(days=3))
    item(db, "due", NOW - timedelta(days=2))
    plan = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, as_of=NOW)
    assert plan["scan"]["due_incomplete"] and plan["scan"]["due_examined"] == 1
    assert plan["items"] == [] and plan["corpus_status"] == "not_scanned"


def test_deduplication_spans_due_and_new_corpus_versions():
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v2','fixture','hash2')"
    )
    db.connection.commit()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 100, version="v1")
    puzzle(db, "same", FEN_A.replace("0 1", "4 9"), "g8h8 c5f8", 100, version="v2")
    item(db, "same", NOW - timedelta(hours=1), version="v2")
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert [(row["kind"], row["corpus_version"]) for row in plan["items"]] == [("due", "v2")]


def add_reviewed_game(db, index, move="e4d3", *, fen="8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1"):
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["Event"] = f"Fixture {index}"
    game.headers["White"] = "Learner"
    game.headers["Black"] = "Opponent"
    game.headers["UTCDate"] = "2026.10.01"
    game.headers["UTCTime"] = "12:00:00"
    game.add_variation(board.parse_uci(move))
    ingest_pgn(db, str(game))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    result = record_game_opportunities(db, game_id, learner="learner")
    evidence_id = cast(list[int], result[0]["evidence_ids"])[0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    return evidence_id


def test_weakness_reason_uses_only_independent_reviewed_evidence():
    db = database()
    puzzle(db, "new", FEN_A, "g8h8 c5f8", 500)
    flipped = chess.Board("8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1").transform(chess.flip_horizontal).fen()
    ids = [
        add_reviewed_game(db, 1),
        add_reviewed_game(db, 2, move="d4e3", fen=flipped),
        add_reviewed_game(db, 3, move="e4c2"),
    ]
    before = db.connection.total_changes
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert db.connection.total_changes == before
    assert plan["evidence"]["state"] == "supported_weakness"
    assert plan["evidence"]["context_count"] == 3
    assert plan["evidence"]["supporting_evidence_ids"] == ids
    assert plan["items"][0]["evidence_ref"] == plan["evidence"]["ref"] == "mate_in_one"
    assert "supported" in plan["items"][0]["reason"]
    review_evidence(db, ids[0], decision="revoke", actor="fixture-reviewer")
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["evidence"]["state"] == "insufficient_evidence"
    assert ids[0] not in plan["evidence"]["supporting_evidence_ids"]


def test_select_complete_review_then_schedule_changes_plan():
    db = database()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 500)
    puzzle(db, "b", FEN_B, "g8h8 b5b8", 600)
    initial = daily_plan(db, subject="learner", corpus_version="v1", limit=1)
    selected = initial["items"][0]
    assert selected["kind"] == "new" and selected["puzzle_id"] == "a"
    training_id = create_training_item(
        db,
        source_type="puzzle",
        source_ref=puzzle_training_ref(selected["corpus_version"], selected["puzzle_id"]),
        skill="mate_in_one",
        operation="execute",
    )
    due = daily_plan(db, subject="learner", corpus_version="v1", limit=1)
    assert due["items"][0]["kind"] == "due" and due["items"][0]["item_id"] == training_id
    start_attempt(db, attempt_id="fixture-attempt", version="v1", puzzle_id="a")
    completed = submit_training_move(
        db,
        "fixture-attempt",
        event_id="terminal",
        move="c5c8",
        item_id=training_id,
        subject="learner",
    )
    review_evidence(
        db, completed["training"]["evidence_id"], decision="accept", actor="fixture-reviewer"
    )
    next_plan = daily_plan(db, subject="learner", corpus_version="v1", limit=1)
    assert next_plan["items"][0]["puzzle_id"] == "b"
    assert next_plan["items"][0]["kind"] == "new"
    assert next_plan["evidence"]["state"] == "insufficient_evidence"
    assert next_plan["evidence"]["context_count"] == 1
    assert next_plan["evidence"]["supporting_evidence_ids"] == [
        completed["training"]["evidence_id"]
    ]
    assert "training_context_unavailable" not in next_plan["evidence"]["exclusions"]


@pytest.mark.parametrize("limit,scan_limit", [(0, 200), (51, 200), (1, 0), (1, 1001), (True, 200)])
def test_limits_are_bounded(limit, scan_limit):
    db = database()
    with pytest.raises(ValueError):
        daily_plan(db, subject="learner", corpus_version="v1", limit=limit, scan_limit=scan_limit)


def test_planning_preserves_outer_transaction_and_never_commits_pending_work():
    db = database()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 100)
    db.connection.execute("UPDATE puzzle_corpora SET source='pending' WHERE version='v1'")
    before = db.connection.total_changes
    assert daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)["items"]
    assert db.connection.in_transaction and db.connection.total_changes == before
    db.connection.rollback()
    assert db.connection.execute("SELECT source FROM puzzle_corpora").fetchone()[0] == "fixture"


def test_theme_label_does_not_override_nonmating_expected_move():
    db = database()
    puzzle(db, "nonmate", FEN_A, "g8h8 c5a5", 100, themes='["mateIn1"]')
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["items"] == []
    assert plan["corpus_status"] == "no_new_candidates"


def test_cli_daily_plan_is_json_and_does_not_reveal_solution(capsys):
    from chess_coach.cli import COMMANDS
    from chess_coach.cli_parser import build_parser

    db = database()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 500)
    args = build_parser().parse_args(["daily-plan", "v1", "--subject", "learner", "--limit", "1"])
    COMMANDS[args.command](db, args)
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["items"][0]["puzzle_id"] == "a"
    assert "c5f8" not in output


def test_puzzle_scan_uses_ordered_composite_index():
    db = database()
    query_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT p.*, c.version FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? ORDER BY p.rating,p.puzzle_id LIMIT ?""",
        ("v1", 3),
    ).fetchall()
    details = [row[3] for row in query_plan]
    assert any("idx_puzzles_curriculum" in detail for detail in details)
    assert not any("TEMP B-TREE" in detail for detail in details)


def test_schema_index_upgrade_is_atomic_and_preserves_puzzles(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_curriculum_index", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=12")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v1','fixture','hash')"
    )
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES ('p1',1,?,'','g8h8 c5f8',100,80,'[]','execute')""",
        (FEN_A,),
    )
    db.connection.commit()
    original = db_recent.add_curriculum_index

    def fail(connection):
        original(connection)
        raise RuntimeError("injected index migration")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_curriculum_index", fail)
        with pytest.raises(RuntimeError, match="injected index migration"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 12
    assert (
        db.connection.execute(
            "SELECT name FROM sqlite_master WHERE name='idx_puzzles_curriculum'"
        ).fetchone()
        is None
    )
    db.initialize()
    db.initialize()
    assert db.connection.execute("SELECT puzzle_id FROM puzzles").fetchone()[0] == "p1"
    assert db.connection.execute(
        "SELECT name FROM sqlite_master WHERE name='idx_puzzles_curriculum'"
    ).fetchone()
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_repeated_reviewed_same_game_is_one_shared_supporting_context():
    from chess_coach.fact_runs import record_fact_run
    from chess_coach.mapping_runs import record_mapping_run_in_transaction
    from chess_coach.mapping_transaction import mapping_transaction

    db = database()
    puzzle(db, "new", FEN_A, "g8h8 c5f8", 500)
    original = add_reviewed_game(db, 1)
    row = db.connection.execute(
        "SELECT position_id,observation_at FROM evidence_mappings WHERE id=?", (original,)
    ).fetchone()
    fact = record_fact_run(
        db,
        position_id=row["position_id"],
        producer="independent-fixture",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "mate_in_one", "payload": {}}],
    )
    with mapping_transaction(db):
        mapping = record_mapping_run_in_transaction(
            db,
            position_id=row["position_id"],
            producer="independent-fixture",
            mapper_version="v1",
            subject="learner",
            operation="execute",
            scope_key="fixture",
            input_data={},
            mappings=[
                {
                    "skill": "mate_in_one",
                    "outcome": "failure",
                    "confidence": 1,
                    "fact_ids": fact["fact_ids"],
                    "context": {},
                    "observation_at": row["observation_at"],
                }
            ],
        )
    duplicate = mapping["evidence_ids"][0]
    review_evidence(db, duplicate, decision="accept", actor="fixture-reviewer")
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["evidence"]["context_count"] == 1
    assert len(plan["evidence"]["supporting_evidence_ids"]) == 1
    assert plan["evidence"]["exclusions"]["duplicate_context"] == 1
    assert plan["items"][0]["evidence_ref"] == plan["evidence"]["ref"]


def collect_pages(db, *, version="v1", scan_limit=1, limit=10):
    cursor = None
    pages = []
    for _ in range(50):
        page = daily_plan(
            db,
            subject="learner",
            corpus_version=version,
            as_of=NOW,
            limit=limit,
            scan_limit=scan_limit,
            cursor=cursor,
        )
        assert page["scan"]["due_examined"] <= scan_limit
        assert page["scan"]["corpus_examined"] <= scan_limit
        assert page["scan"]["scheduled_examined"] <= scan_limit
        pages.append(page)
        cursor = page["next_cursor"]
        if cursor is None:
            return pages
    raise AssertionError("continuation did not terminate")


def test_future_scheduled_prompt_copy_is_excluded_across_corpus_versions():
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v2','fixture','hash2')"
    )
    db.connection.commit()
    puzzle(db, "copy", FEN_A, "g8h8 c5f8", 100, version="v1")
    puzzle(db, "later", FEN_A.replace("0 1", "17 40"), "g8h8 c5f8", 100, version="v2")
    puzzle(db, "distinct", FEN_B, "g8h8 b5b8", 200, version="v1")
    item(db, "later", NOW + timedelta(days=1), version="v2")
    pages = collect_pages(db, scan_limit=1)
    found = [row["puzzle_id"] for page in pages for row in page["items"]]
    assert found == ["distinct"]
    assert all(row["kind"] == "new" for page in pages for row in page["items"])


def test_continuation_reaches_late_valid_candidate_past_unsupported_prefix():
    db = database()
    for number in range(3):
        puzzle(db, f"bad{number}", chess.STARTING_FEN, "e2e4 e7e5", number + 10)
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 100)
    pages = collect_pages(db, scan_limit=1)
    assert len(pages) >= 4
    assert all(page["continuation_reason"] == "corpus_scan_incomplete" for page in pages[:-1])
    assert [row["puzzle_id"] for page in pages for row in page["items"]] == ["late"]


def test_due_pagination_finishes_before_new_material():
    db = database()
    for number in range(3):
        name = f"bad{number}"
        puzzle(db, name, chess.STARTING_FEN, "e2e4 e7e5", number + 10)
        item(db, name, NOW - timedelta(days=4 - number))
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 100)
    puzzle(db, "new", FEN_B, "g8h8 b5b8", 200)
    item(db, "due", NOW - timedelta(hours=1))
    pages = collect_pages(db, scan_limit=1)
    selections = [row for page in pages for row in page["items"]]
    assert [(row["kind"], row["puzzle_id"]) for row in selections] == [
        ("due", "due"),
        ("new", "new"),
    ]
    for page in pages:
        if page["scan"]["due_incomplete"]:
            assert all(row["kind"] == "due" for row in page["items"])
            assert page["scan"]["corpus_examined"] == 0


def test_scheduled_conflict_scan_continues_before_returning_a_candidate():
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v2','fixture','hash2')"
    )
    db.connection.commit()
    puzzle(db, "copy", FEN_A, "g8h8 c5f8", 100)
    puzzle(db, "unrelated", FEN_B, "g8h8 b5b8", 100, version="v2")
    puzzle(db, "future", FEN_A, "g8h8 c5f8", 200, version="v2")
    item(db, "unrelated", NOW + timedelta(days=1), version="v2")
    item(db, "future", NOW + timedelta(days=1), version="v2")
    pages = collect_pages(db, scan_limit=1)
    assert pages[0]["continuation_reason"] == "scheduled_scan_incomplete"
    assert all(not page["items"] for page in pages)


def test_cursor_rejects_changed_sources_scope_and_time():
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "later", FEN_A, "g8h8 c5f8", 200)
    page = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW, scan_limit=1)
    cursor = page["next_cursor"]
    assert cursor
    with pytest.raises(ValueError, match="scope changed"):
        daily_plan(db, subject="other", corpus_version="v1", as_of=NOW, scan_limit=1, cursor=cursor)
    with pytest.raises(ValueError, match="time changed"):
        daily_plan(
            db,
            subject="learner",
            corpus_version="v1",
            as_of=NOW + timedelta(seconds=1),
            scan_limit=1,
            cursor=cursor,
        )
    db.connection.execute("UPDATE puzzles SET rating=rating+1 WHERE puzzle_id='later'")
    db.connection.commit()
    with pytest.raises(ValueError, match="sources changed"):
        daily_plan(
            db, subject="learner", corpus_version="v1", as_of=NOW, scan_limit=1, cursor=cursor
        )


def test_mastery_projection_does_not_invalidate_cursor():
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 200)
    page = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW, scan_limit=1)
    cursor = page["next_cursor"]
    db.connection.execute("""INSERT INTO mastery_states
        (subject,skill,operation,mastery,uncertainty,evidence_weight,trend_30d,updated_at,model_version)
        VALUES ('learner','mate_in_one','execute',0.5,0.5,1,NULL,'2026-01-01','fixture')""")
    db.connection.commit()
    next_page = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, cursor=cursor)
    assert next_page["as_of"] == page["as_of"]
    assert next_page["items"][0]["puzzle_id"] == "late"


@pytest.mark.parametrize(
    "field,value",
    [
        ("scheduled_after", -1),
        ("limit", True),
        ("due_after", [float("nan"), 1]),
        ("seen", [{}]),
        ("phase", "unsupported"),
        ("v", True),
        ("new_after", [-1, "puzzle"]),
    ],
)
def test_malformed_cursor_is_rejected(field, value):
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 200)
    cursor = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, as_of=NOW)[
        "next_cursor"
    ]
    raw = base64.urlsafe_b64decode(cursor)
    state = json.loads(raw[32:])
    state[field] = value
    payload = json.dumps(state).encode()
    key = db.connection.execute("SELECT cursor_key FROM curriculum_source_revision").fetchone()[0]
    signature = hmac.digest(key, payload, hashlib.sha256)
    forged = base64.urlsafe_b64encode(signature + payload).decode()
    with pytest.raises(ValueError, match="invalid curriculum cursor"):
        daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, cursor=forged)


def test_invalid_legacy_now_due_does_not_break_index_upgrade(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_curriculum_index", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=12")
    db.connection.execute("""INSERT INTO training_items
        (source_type,source_ref,skill,operation,due,scheduler_version)
        VALUES('puzzle','legacy','mate_in_one','execute','now','old')""")
    db.connection.commit()
    db.initialize()
    assert db.connection.execute("SELECT due FROM training_items").fetchone()[0] == "now"


def test_continuation_passes_one_thousand_unsupported_rows():
    db = database()
    db.connection.executemany(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES (?,1,?,'','e2e4 e7e5',?,80,'[]','recognize')""",
        [(f"bad-{i:04d}", chess.STARTING_FEN, i + 1) for i in range(1000)],
    )
    db.connection.commit()
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 2000)
    first = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1000, as_of=NOW)
    assert first["items"] == [] and first["scan"]["corpus_examined"] == 1000
    assert first["continuation_reason"] == "corpus_scan_incomplete"
    second = daily_plan(
        db, subject="learner", corpus_version="v1", scan_limit=1000, cursor=first["next_cursor"]
    )
    assert [item["puzzle_id"] for item in second["items"]] == ["late"]


def test_due_and_scheduled_continuation_use_bounded_indexes():
    db = database()
    due_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT id,source_ref,due,julianday(due) AS due_order
        FROM training_items INDEXED BY idx_curriculum_due
        WHERE source_type='puzzle' AND skill='mate_in_one' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)
        AND (julianday(due),id) > (?,?) ORDER BY julianday(due),id LIMIT ?""",
        (NOW.isoformat(), 2400000.0, 1, 4),
    ).fetchall()
    due_details = [row[3] for row in due_plan]
    assert any("idx_curriculum_due" in detail for detail in due_details)
    assert not any("TEMP B-TREE" in detail for detail in due_details)
    scheduled_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT id,source_ref FROM training_items INDEXED BY idx_curriculum_scheduled
        WHERE id>? AND source_type='puzzle' AND skill='mate_in_one' AND operation='execute'
        ORDER BY id LIMIT ?""",
        (0, 4),
    ).fetchall()
    scheduled_details = [row[3] for row in scheduled_plan]
    assert any("idx_curriculum_scheduled" in detail for detail in scheduled_details)
    assert not any("TEMP B-TREE" in detail for detail in scheduled_details)


def test_keyset_pagination_preserves_many_equal_rating_and_due_ties():
    db = database()
    for number in range(4):
        name = f"bad{number}"
        puzzle(db, name, chess.STARTING_FEN, "e2e4 e7e5", 100)
        item(db, name, NOW - timedelta(days=1))
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 100)
    item(db, "late", NOW - timedelta(days=1))
    pages = collect_pages(db, scan_limit=1, limit=1)
    assert [entry["puzzle_id"] for page in pages for entry in page["items"]] == ["late"]
    assert sum(page["scan"]["due_examined"] for page in pages) >= 5


def test_equal_key_continuation_seeks_both_columns():
    db = database()
    due_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT id FROM training_items INDEXED BY idx_curriculum_due
        WHERE source_type='puzzle' AND skill='mate_in_one' AND operation='execute'
        AND lower(due) != 'now' AND julianday(due) <= julianday(?)
        AND julianday(due)=? AND id>? ORDER BY id LIMIT ?""",
        (NOW.isoformat(), 2400000.0, 1, 2),
    ).fetchall()
    assert any("idx_curriculum_due" in row[3] and "id>?" in row[3] for row in due_plan)
    assert not any("TEMP B-TREE" in row[3] for row in due_plan)
    corpus_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT p.puzzle_id FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND p.rating>=0 AND p.rating=? AND p.puzzle_id>?
        ORDER BY p.puzzle_id LIMIT ?""",
        ("v1", 100, "a", 2),
    ).fetchall()
    assert any(
        "idx_puzzles_curriculum" in row[3] and "puzzle_id>?" in row[3] for row in corpus_plan
    )
    assert not any("TEMP B-TREE" in row[3] for row in corpus_plan)


def test_valid_looking_forged_phase_cannot_bypass_due_priority():
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 200)
    item(db, "bad", NOW - timedelta(days=2))
    item(db, "due", NOW - timedelta(days=1))
    cursor = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW, scan_limit=1)[
        "next_cursor"
    ]
    raw = base64.urlsafe_b64decode(cursor)
    state = json.loads(raw[32:])
    state["phase"] = "new"
    forged = base64.urlsafe_b64encode(raw[:32] + json.dumps(state).encode()).decode()
    with pytest.raises(ValueError, match="invalid curriculum cursor"):
        daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, cursor=forged)


def test_missing_scheduled_prompt_blocks_new_selection_with_explicit_reason():
    db = database()
    puzzle(db, "new", FEN_A, "g8h8 c5f8", 100)
    unresolved_id = create_training_item(
        db,
        source_type="puzzle",
        source_ref="legacy-unresolved",
        skill="mate_in_one",
        operation="execute",
    )
    db.connection.execute(
        "UPDATE training_items SET due=?", ((NOW + timedelta(days=1)).isoformat(),)
    )
    db.connection.commit()
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["items"] == [] and plan["next_cursor"] is None
    assert plan["continuation_reason"] == "scheduled_prompt_unavailable"
    assert plan["scan"]["scheduled_unavailable"]
    assert plan["scan"]["scheduled_unavailable_item_id"] == unresolved_id
    assert "Restore the referenced versioned corpus" in plan["diagnostic"]


def test_scheduled_nonmating_line_still_blocks_same_prompt_copy():
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v2','fixture','hash2')"
    )
    db.connection.commit()
    puzzle(db, "copy", FEN_A, "g8h8 c5f8", 100, version="v1")
    puzzle(db, "other-line", FEN_A, "g8h8 c5a5", 100, version="v2")
    item(db, "other-line", NOW + timedelta(days=1), version="v2")
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["items"] == []


def test_invalid_negative_ratings_are_reported_and_not_recommended():
    db = database()
    puzzle(db, "bad-rating", FEN_A, "g8h8 c5f8", -1)
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert plan["items"] == []
    assert plan["scan"]["invalid_ratings_present"]


def test_continuation_survives_database_reopen(tmp_path):
    path = tmp_path / "coach.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v1','fixture','hash1')"
    )
    db.connection.commit()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 200)
    first = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, as_of=NOW)
    db.close()
    db = Database(path)
    second = daily_plan(
        db, subject="learner", corpus_version="v1", scan_limit=1, cursor=first["next_cursor"]
    )
    assert second["as_of"] == first["as_of"]
    assert [entry["puzzle_id"] for entry in second["items"]] == ["late"]


def test_due_continuation_passes_one_thousand_unsupported_rows():
    db = database()
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora WHERE version='v1'").fetchone()[0]
    for number in range(1000):
        name = f"unsupported-{number:04d}"
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
            rating_deviation,themes_json,objective) VALUES(?,?,?,'','e2e4 e7e5',100,80,'[]','execute')""",
            (name, corpus, chess.STARTING_FEN),
        )
        db.connection.execute(
            """INSERT INTO training_items(source_type,source_ref,skill,operation,due,scheduler_version)
            VALUES('puzzle',?,'mate_in_one','execute',?,'fixture')""",
            (puzzle_training_ref("v1", name), (NOW - timedelta(days=1)).isoformat()),
        )
    db.connection.commit()
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 100)
    item(db, "due", NOW - timedelta(days=1))
    pages = collect_pages(db, scan_limit=1000, limit=1)
    assert pages[0]["scan"]["due_examined"] == 1000
    assert pages[0]["continuation_reason"] == "due_scan_incomplete"
    assert [entry["puzzle_id"] for page in pages for entry in page["items"]] == ["due"]
    assert any(page["continuation_reason"] == "scheduled_scan_incomplete" for page in pages)


def test_due_conflict_with_missing_source_fails_closed():
    db = database()
    missing = item(db, "missing", NOW - timedelta(days=1))
    puzzle(db, "due", FEN_A, "g8h8 c5f8", 100)
    item(db, "due", NOW - timedelta(hours=1))
    result = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW)
    assert result["items"] == []
    assert result["continuation_reason"] == "scheduled_prompt_unavailable"
    assert result["scan"]["scheduled_unavailable_item_id"] == missing
    assert "repair" in result["diagnostic"]


def test_reviewed_copy_defers_older_due_copy_across_bounded_pages():
    db = database()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 100)
    puzzle(db, "copy", FEN_A.replace("0 1", "9 10"), "g8h8 c5f8", 200)
    first = item(db, "a", NOW - timedelta(days=2))
    second = item(db, "copy", NOW - timedelta(days=1))
    before = collect_pages(db, scan_limit=1, limit=1)
    assert [entry["item_id"] for page in before for entry in page["items"]] == [first]
    result = review_item(db, second, "good", reviewed_at=NOW - timedelta(minutes=1))
    assert datetime.fromisoformat(cast(str, result["due"])) > NOW
    pages = collect_pages(db, scan_limit=1, limit=1)
    assert not [entry for page in pages for entry in page["items"]]
    assert any(page["continuation_reason"] == "scheduled_scan_incomplete" for page in pages)


def test_latest_review_wins_over_an_older_future_copy():
    db = database()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 100)
    puzzle(db, "copy", FEN_A, "g8h8 c5f8", 200)
    older = item(db, "a", NOW + timedelta(days=1))
    newer = item(db, "copy", NOW - timedelta(minutes=1))
    db.connection.execute(
        "UPDATE training_items SET last_review=? WHERE id=?",
        ((NOW - timedelta(days=2)).isoformat(), older),
    )
    db.connection.execute(
        "UPDATE training_items SET last_review=? WHERE id=?",
        ((NOW - timedelta(hours=1)).isoformat(), newer),
    )
    db.connection.commit()
    pages = collect_pages(db, scan_limit=1, limit=1)
    assert [entry["item_id"] for page in pages for entry in page["items"]] == [newer]


def test_cursor_rejects_evidence_review_changes_between_pages():
    db = database()
    puzzle(db, "bad", chess.STARTING_FEN, "e2e4 e7e5", 100)
    puzzle(db, "late", FEN_A, "g8h8 c5f8", 200)
    evidence_id = add_reviewed_game(db, 1)
    first = daily_plan(db, subject="learner", corpus_version="v1", scan_limit=1, as_of=NOW)
    assert first["next_cursor"]
    review_evidence(db, evidence_id, decision="revoke", actor="fixture-reviewer")
    with pytest.raises(ValueError, match="sources changed"):
        daily_plan(
            db, subject="learner", corpus_version="v1", scan_limit=1, cursor=first["next_cursor"]
        )


def test_large_evidence_set_does_not_produce_partial_weakness_inference():
    from chess_coach.evidence import record_evidence

    db = database()
    puzzle(db, "valid", FEN_A, "g8h8 c5f8", 100)
    for _ in range(2):
        record_evidence(
            db,
            skill="mate_in_one",
            operation="execute",
            outcome="failure",
            confidence=1,
            subject="learner",
        )
    plan = daily_plan(db, subject="learner", corpus_version="v1", as_of=NOW, scan_limit=1)
    assert plan["evidence"]["state"] == "evidence_scan_incomplete"
    assert plan["evidence"]["source_rows_examined"] == 1
    assert plan["evidence"]["supporting_evidence_ids"] == []
    assert plan["evidence"]["mastery"] is None
    assert "evidence scan is incomplete" in plan["items"][0]["reason"]


def test_bounded_evidence_probe_uses_composite_index():
    db = database()
    query_plan = db.connection.execute(
        """EXPLAIN QUERY PLAN SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill='mate_in_one' AND operation='execute' ORDER BY id LIMIT ?""",
        ("learner", 2),
    ).fetchall()
    assert any("idx_curriculum_evidence" in row[3] for row in query_plan)
    assert not any("TEMP B-TREE" in row[3] for row in query_plan)


def test_prompt_deduplication_persists_across_due_and_new_pages():
    db = database()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('v2','fixture','hash2')"
    )
    db.connection.commit()
    puzzle(db, "a", FEN_A, "g8h8 c5f8", 100, version="v1")
    puzzle(db, "copy", FEN_A.replace("0 1", "4 9"), "g8h8 c5f8", 100, version="v2")
    puzzle(db, "b", FEN_B, "g8h8 b5b8", 200, version="v1")
    item(db, "a", NOW - timedelta(days=2), version="v1")
    item(db, "copy", NOW - timedelta(days=1), version="v2")
    pages = collect_pages(db, scan_limit=1, limit=2)
    selected = [row for page in pages for row in page["items"]]
    assert [(row["kind"], row["puzzle_id"]) for row in selected] == [("due", "a"), ("new", "b")]
    assert len({row["prompt_key"] for row in selected}) == 2
