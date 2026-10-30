"""Synthetic source-linked check-response report integration."""

import sys
import time

import chess.engine
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.style_report import style_report
from chess_coach.style_schedule_worker import process_schedule
from tests.test_deep_selection import LEARNER
from tests.test_style_schedule import CHECK, CONTROL, SyntheticEngine


def scheduled(db, monkeypatch):
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: SyntheticEngine()
    )
    return process_schedule(
        db,
        PipelineConfig(learner=LEARNER, engine_path=sys.executable),
        deadline=time.monotonic() + 20,
    )


def test_qualified_target_is_defense_only_and_control_is_separate(tmp_path, monkeypatch):
    db = Database(tmp_path / "purpose-report.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    report = style_report(db, LEARNER)
    purpose = [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]
    assert len(purpose) == 1
    assert purpose[0]["context"]["in_check"] is True
    assert purpose[0]["allocation"] == "purpose_target"
    assert purpose[0]["eligible_dimensions"] == [
        "defense_king",
        "defense_capture",
        "defense_interpose",
        "defense_countercheck",
    ]
    assert report["purpose_coverage"]["counts"]["target_comparable"] == 1
    assert report["purpose_coverage"]["counts"]["control_outside_check"] == 1
    assert report["dimensions"]["simplification"]["no_contrast"] == 0
    assert report["coverage"]["outcomes"]["unknown"] == 2
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0


def test_report_reuses_each_game_history_and_private_views_are_read_only(
    tmp_path, monkeypatch, capsys
):
    import json

    import chess_coach.purpose_source as source
    import chess_coach.style_purpose_collect as collect
    from chess_coach.cli import main
    from tests.purpose_browser_fixtures import app, browser_get
    from tests.purpose_db_snapshot import schema_objects, typed_rows

    path = tmp_path / "private-report.sqlite"
    db = Database(path)
    db.initialize()
    scheduled(db, monkeypatch)
    calls = []
    original = collect.selected_boards

    def counted(database, game_id, ids):
        calls.append(game_id)
        return original(database, game_id, ids)

    monkeypatch.setattr(collect, "selected_boards", counted)
    monkeypatch.setattr(
        source,
        "selected_boards",
        lambda *_a: (_ for _ in ()).throw(AssertionError("unbatched replay")),
    )
    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("report started engine")),
    )
    tables = [row[1] for row in schema_objects(db) if row[0] == "table"]
    before = typed_rows(db, tables)
    report = style_report(db, LEARNER)
    assert sorted(calls) == [1, 2]
    assert report["purpose_schedule"]["slots"][0]["source_state"] == "current"
    assert before == typed_rows(db, tables)
    calls.clear()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["coverage"]["effective_game_limit"] == 100
    assert cli["purpose_coverage"]["counts"]["target_comparable"] == 1
    page = browser_get(app(path).test_client(), "/style-choices")
    assert page.status_code == 200
    assert b"not a global-best ranking" in page.data
    assert b"purpose_target" in page.data
    assert b"effective maximum 10" in page.data
    assert before == typed_rows(db, tables)


def test_changed_policy_makes_purpose_result_unknown(tmp_path, monkeypatch):
    import chess_coach.purpose_config as config

    db = Database(tmp_path / "stale-policy.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    monkeypatch.setattr(config, "FINAL_NODES", config.FINAL_NODES + 1)
    report = style_report(db, LEARNER)
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]
    assert report["purpose_coverage"]["counts"]["target_stale"] == 1
    assert report["purpose_schedule"]["slots"][0]["source_state"] == "stale"


def test_duplicate_purpose_slots_count_one_vote(tmp_path, monkeypatch):
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.fact_fingerprint import canonical

    db = Database(tmp_path / "duplicate.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    old = db.connection.execute("SELECT * FROM style_schedule_slots WHERE kind='target'").fetchone()
    cycle = db.connection.execute(
        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
        (learner_key(LEARNER), 1, canonical({})),
    ).lastrowid
    db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
        VALUES(?,?,?,?,?,?,?)""",
        (
            cycle,
            "control",
            old["game_id"],
            old["position_id"],
            "complete",
            "comparable",
            old["request_id"],
        ),
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    purpose = [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]
    assert len(purpose) == 1
    assert purpose[0]["allocation"] == "purpose_control"
    assert report["purpose_coverage"]["counts"]["target_duplicate"] == 1
    assert report["purpose_coverage"]["counts"]["control_comparable"] == 1


def mixed_source(db_path, monkeypatch, *, ordinary):
    import io

    import chess
    import chess.pgn

    import tests.test_deep_selection as selection_tests
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.fact_fingerprint import canonical
    from chess_coach.purpose_request import create
    from chess_coach.purpose_worker import run
    from tests.test_deep_execution import DeepEngine, options, use_engine
    from tests.test_style_defense_integration import PGN, synthetic_paths

    game = chess.pgn.read_game(io.StringIO(PGN))
    assert game is not None
    played = list(game.mainline_moves())
    monkeypatch.setattr(selection_tests, "PGN", PGN)
    db = selection_tests.setup_game(db_path, monkeypatch)
    selection = select_deep(db, [1], learner=LEARNER, per_game=100, total=100)
    if ordinary:

        class Engine(DeepEngine):
            def analyse(self, board, limit, multipv, root_moves=None):
                roots = root_moves or [played[len(board.move_stack)]]
                if root_moves is None and len(board.move_stack) == 7:
                    roots = [chess.Move.from_uci("c7c6"), chess.Move.from_uci("e8d8")]
                elif root_moves is None:
                    roots += [move for move in board.legal_moves if move not in roots][
                        : multipv - 1
                    ]
                return [
                    {
                        "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                        "pv": pv,
                        "nodes": 200,
                        "depth": 5,
                        "time": 0.05,
                    }
                    for pv in synthetic_paths(board, roots)
                ]

        use_engine(monkeypatch, Engine(db))
        run_deep(
            db,
            selection["games"][0]["selection_id"],
            learner=LEARNER,
            options=options(multipv=2, max_jobs=20),
        )
    position_id = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=8"
    ).fetchone()[0]
    request_id = create(db, position_id, LEARNER, engine_path=sys.executable)["request_id"]
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: SyntheticEngine())
    assert run(db, request_id, LEARNER)["status"] == "complete"
    cycle = db.connection.execute(
        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
        (learner_key(LEARNER), 0, canonical({})),
    ).lastrowid
    db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
        VALUES(?,?,?,?,?,?,?)""",
        (cycle, "target", 1, position_id, "complete", "comparable", request_id),
    )
    db.connection.commit()
    return db, position_id


def test_current_ordinary_precedes_duplicate_purpose(tmp_path, monkeypatch):
    db, position_id = mixed_source(tmp_path / "mixed.sqlite", monkeypatch, ordinary=True)
    report = style_report(db, LEARNER)
    choices = [item for item in report["observations"] if item["position_id"] == position_id]
    assert len(choices) == 1
    assert choices[0]["provenance"] == "ordinary_deep"
    assert choices[0]["context"]["color"] == "black"
    assert choices[0]["choices"]["defense_interpose"] == "interposition"
    assert report["purpose_coverage"]["counts"]["target_duplicate"] == 1


def test_unqualified_ordinary_does_not_veto_black_purpose(tmp_path, monkeypatch):
    db, position_id = mixed_source(
        tmp_path / "pending-ordinary.sqlite", monkeypatch, ordinary=False
    )
    report = style_report(db, LEARNER)
    choices = [item for item in report["observations"] if item["position_id"] == position_id]
    assert len(choices) == 1
    assert choices[0]["provenance"] == "purpose_candidate_set"
    assert choices[0]["context"]["color"] == "black"
    assert report["purpose_coverage"]["counts"]["target_comparable"] == 1


@pytest.mark.parametrize("mode", ["mate", "bound", "depth", "short", "missing_played"])
def test_unusable_final_search_never_becomes_a_style_vote(tmp_path, monkeypatch, mode):
    class Unusable(SyntheticEngine):
        def analyse(self, board, _limit, multipv, root_moves=None):
            lines = super().analyse(board, _limit, multipv, root_moves)
            if root_moves is None:
                return lines
            if mode == "mate":
                lines[0]["score"] = chess.engine.PovScore(chess.engine.Mate(2), board.turn)
            elif mode == "bound":
                lines[0]["lowerbound"] = True
            elif mode == "depth":
                lines[0]["depth"] += 1
            elif mode == "short":
                lines[0]["pv"] = lines[0]["pv"][:1]
            elif mode == "missing_played":
                return lines[1:]
            return lines

    db = Database(tmp_path / f"{mode}.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda *_a, **_k: Unusable())
    process_schedule(
        db,
        PipelineConfig(learner=LEARNER, engine_path=sys.executable),
        deadline=time.monotonic() + 20,
    )
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_insufficient"] == 1
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]


def test_linked_request_must_match_slot_game_and_decision(tmp_path, monkeypatch):
    db = Database(tmp_path / "cross-linked.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    control_request = db.connection.execute(
        "SELECT request_id FROM style_schedule_slots WHERE kind='control'"
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE style_schedule_slots SET request_id=? WHERE kind='target'", (control_request,)
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_source_unknown"] == 1
    assert report["purpose_schedule"]["slots"][0]["source_state"] == "unavailable"
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]


def test_older_cycle_truncation_remains_explicit_unknown(tmp_path, monkeypatch):
    from chess_coach.deep_selection_source import learner_key

    db = Database(tmp_path / "cycle-limit.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    db.connection.executemany(
        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
        [(learner_key(LEARNER), number, "{}") for number in range(1, 102)],
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["examined_cycles"] == 100
    assert report["purpose_coverage"]["older_cycles_unknown"] is True
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]


def test_unlinked_pending_slot_is_explicit_and_not_a_vote(tmp_path):
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.purpose_request import create

    db = Database(tmp_path / "pending.sqlite")
    db.initialize()
    ingest_pgn(db, CHECK)
    position_id = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=9"
    ).fetchone()[0]
    request_id = create(db, position_id, LEARNER, engine_path=sys.executable)["request_id"]
    cycle = db.connection.execute(
        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
        (learner_key(LEARNER), 0, "{}"),
    ).lastrowid
    db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
        VALUES(?,?,?,?,?,?,?)""",
        (cycle, "target", 1, position_id, "pending", "queued", request_id),
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_pending"] == 1
    assert report["purpose_schedule"]["slots"][0]["status"] == "pending"
    assert not report["observations"]


def test_newer_cross_link_does_not_poison_valid_request_cache(tmp_path, monkeypatch):
    from chess_coach.deep_selection_source import learner_key

    db = Database(tmp_path / "cross-link-order.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    target = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE kind='target'"
    ).fetchone()
    control = db.connection.execute(
        "SELECT * FROM style_schedule_slots WHERE kind='control'"
    ).fetchone()
    cycle = db.connection.execute(
        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
        (learner_key(LEARNER), 1, "{}"),
    ).lastrowid
    db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
        VALUES(?,?,?,?,?,?,?)""",
        (
            cycle,
            "target",
            target["game_id"],
            target["position_id"],
            "complete",
            "synthetic",
            control["request_id"],
        ),
    )
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_source_unknown"] == 1
    assert report["purpose_coverage"]["counts"]["target_comparable"] == 1
    assert (
        len(
            [
                item
                for item in report["observations"]
                if item.get("provenance") == "purpose_candidate_set"
            ]
        )
        == 1
    )


def test_changed_game_source_is_excluded_as_unknown(tmp_path, monkeypatch):
    db = Database(tmp_path / "changed-source.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
    db.connection.commit()
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_outside_sample"] == 1
    assert report["purpose_schedule"]["slots"][0]["source_state"] == "stale"
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]


def test_complete_status_without_immutable_attempt_is_insufficient():
    from chess_coach.style_purpose_view_state import view_state
    from chess_coach.style_schedule_view_state import view_state as schedule_state

    view = {"source_state": "current", "status": "complete", "attempts": []}
    assert view_state(view) == "insufficient"
    assert schedule_state(view) == "insufficient"


def test_report_snapshot_rechecks_changed_source_on_next_read(tmp_path, monkeypatch):
    import sqlite3

    import chess_coach.style_purpose_collect as collect

    path = tmp_path / "snapshot.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute("PRAGMA journal_mode=WAL")
    scheduled(db, monkeypatch)
    original = collect.selected_boards
    changed = []

    def concurrent_change(database, game_id, ids):
        if not changed and game_id == 1:
            other = sqlite3.connect(path)
            other.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
            other.commit()
            other.close()
            changed.append(True)
        return original(database, game_id, ids)

    monkeypatch.setattr(collect, "selected_boards", concurrent_change)
    first = style_report(db, LEARNER)
    assert first["purpose_coverage"]["counts"]["target_comparable"] == 1
    assert changed == [True]
    second = style_report(db, LEARNER)
    assert second["purpose_coverage"]["counts"]["target_outside_sample"] == 1
    assert second["purpose_schedule"]["slots"][0]["source_state"] == "stale"
    db.close()


def test_unavailable_shared_history_is_not_replayed_for_status(tmp_path, monkeypatch):
    import chess_coach.purpose_source as source
    import chess_coach.style_purpose_collect as collect

    db = Database(tmp_path / "missing-history.sqlite")
    db.initialize()
    scheduled(db, monkeypatch)
    original = collect.selected_boards

    def missing(database, game_id, ids):
        return {} if game_id == 1 else original(database, game_id, ids)

    monkeypatch.setattr(collect, "selected_boards", missing)
    monkeypatch.setattr(source, "selected_boards", lambda *_a: pytest.fail("history replayed"))
    report = style_report(db, LEARNER)
    assert report["purpose_coverage"]["counts"]["target_source_unknown"] == 1
    assert report["purpose_schedule"]["slots"][0]["source_state"] == "unavailable"
    assert not [
        item for item in report["observations"] if item.get("provenance") == "purpose_candidate_set"
    ]
