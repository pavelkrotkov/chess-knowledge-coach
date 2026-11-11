"""Pin observations retain their current source and stay outside mastery."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app


class Engine:
    def __init__(self):
        self.id = {"name": "synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        moves = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": moves,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def test_source_review_and_closed_mastery(tmp_path, monkeypatch):
    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("b4c4"))
    board.push_uci("b4c4")
    node.add_variation(board.parse_uci("h6h5"))
    path = tmp_path / "pin.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_learner", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, "fixture_learner", "execute")
    assert result["outcome"] == "success"
    evidence_id = result["evidence_ids"][0]
    detail = inspect_evidence(db, evidence_id)
    assert detail["pin_source_currentness"] == "current"
    assert detail["pin_explanation"]["proof"]["san"] == "Rc4"
    assert process_decision(db, 1, "fixture_learner", "execute")["replayed"]
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("spoof", result["mapping_run_id"])
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "stale"
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("1.0.1", result["mapping_run_id"])
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "current"
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, "fixture_learner", "absolute_pin", "execute", datetime.now(UTC)
    )
    assert not eligible and excluded["pin_family_unvalidated"] == 1
    app = create_app(
        db_path=path,
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200 and b"Pin source: current" in page.data and b"Rc4" in page.data
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "stale"


def test_bounded_worker_publishes_relative_prevention_and_browser_explanation(
    tmp_path, monkeypatch
):
    from chess_coach.pin_worker import process_pins

    board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("e2f2"))
    board.push_uci("e2f2")
    node.add_variation(board.parse_uci("e3e1"))
    path = tmp_path / "pin-defense.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_learner", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    from chess_coach.pin_plan import report as pin_report

    assert process_pins(db, config, "prevent")["outcomes"]["failure"] == 1
    assert pin_report(db, "fixture_learner")["source"] is None

    # Same geometry in separate dated games: one further miss and one defense.
    for date, first, reply in (
        ("2026.01.02", "e2f2", "e3e1"),
        ("2026.01.03", "e2e3", "h8g8"),
    ):
        other = chess.pgn.Game()
        other_board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
        other.setup(other_board)
        other.headers.update(
            {
                "White": "fixture_learner",
                "Black": "fixture_opponent",
                "Result": "*",
                "UTCDate": date,
                "UTCTime": "12:00:00",
            }
        )
        node = other.add_variation(other_board.parse_uci(first))
        other_board.push_uci(first)
        node.add_variation(other_board.parse_uci(reply))
        ingest_pgn(db, str(other))
        game_id = db.connection.execute("SELECT max(id) FROM games").fetchone()[0]
        assert (
            run_analysis(
                db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
            )["status"]
            == "complete"
        )
    report = process_pins(db, config, "prevent")
    assert report["outcomes"]["failure"] == 1
    assert report["outcomes"]["success"] == 1

    from chess_coach.recurrence_cursor import MAX_ID
    from chess_coach.recurrence_sources import evidence as recurrence_evidence

    def outcomes(**options):
        rows, _ = recurrence_evidence(
            db, "fixture_learner", "relative_pin", "prevent", MAX_ID, **options
        )
        return [row["outcome"] for row in rows]

    assert outcomes(failure_only=True) == ["failure", "failure"]
    assert outcomes(outcome="success") == ["success"]
    assert outcomes(failure_only=True, outcome="success") == ["failure", "failure"]
    selected = pin_report(db, "fixture_learner")["source"]
    assert selected and selected["repeated_miss"] and selected["games"] == 2
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?",
        ("relative_pin", "prevent"),
    ).fetchone()
    evidence = inspect_evidence(db, row["id"])
    assert evidence["pin_source_currentness"] == "current"
    assert evidence["pin_explanation"]["proof"]["san"] == "Rxe1"
    review_evidence(db, row["id"], decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, "fixture_learner", "relative_pin", "prevent", datetime.now(UTC)
    )
    assert not eligible and excluded["pin_family_unvalidated"] == 1
    app = create_app(
        db_path=path,
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    evidence_id = row["id"]
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"Pin source: current" in page.data and b"Rxe1" in page.data and b"Rxe3" in page.data

    from chess_coach.objective_worker import process
    from tests.test_unified_sessions import token

    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    base = "https://coach.invalid"
    plan = client.get("/plan", base_url=base, headers=headers)
    assert b"/plan/pin-defense" in plan.data
    choice = client.get("/plan/pin-defense", base_url=base, headers=headers)
    assert b"matching missed defense" in choice.data and b"pins your piece" in choice.data
    assert client.get("/plan/pin-defense", base_url=base).status_code == 403
    start = client.post(
        "/unified/start",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": token(choice, "csrf"),
            "source_type": "own-game",
            "version": token(choice, "version"),
            "key": token(choice, "key"),
        },
    )
    assert start.status_code == 303
    practice = client.get(start.headers["Location"], base_url=base, headers=headers)
    assert b"Remove the named pinner" in practice.data
    move = client.post(
        "/unified/move",
        base_url=base,
        headers=headers | {"Origin": base},
        data={
            "csrf": token(practice, "csrf"),
            "attempt": token(practice, "attempt"),
            "event": token(practice, "event"),
            "move": "e2e3",
        },
    )
    assert move.status_code == 303
    assert process(db, "fixture_learner")["outcomes"] == {"correct": 1}
    result = client.get(move.headers["Location"], base_url=base, headers=headers)
    assert b"stated bounded pin defense is verified" in result.data

    # A rejected miss cannot support a repeated-miss claim; the success is a rehearsal.
    review_evidence(db, selected["evidence_id"], decision="reject", actor="fixture_reviewer")
    fallback = pin_report(db, "fixture_learner")["source"]
    assert fallback and not fallback["repeated_miss"]
    assert (
        b"Diagnostic rehearsal"
        in client.get("/plan/pin-defense", base_url=base, headers=headers).data
    )

    # Reimports of the same game do not create recurrence, and pin policies stay distinct.
    from copy import deepcopy

    from chess_coach.objective_pin_prevent_contract import VERSION
    from chess_coach.objective_pin_prevent_source import resolve
    from chess_coach.pin_plan_pattern import pattern
    from chess_coach.pin_plan_select import select

    snapshot = resolve(db, VERSION, fallback["key"], "fixture_learner")
    item = {
        "id": fallback["evidence_id"],
        "game_key": "same-game",
        "outcome": "success",
        "version": snapshot["provenance"]["mapper_version"],
    }
    assert select({"pattern": [(item, snapshot), (item, snapshot)]}) is None
    other = deepcopy(snapshot)
    other["provenance"]["pin_prevention"]["kind"] = "absolute_pin"
    assert pattern(snapshot, item) != pattern(other, item)
    other = deepcopy(snapshot)
    other["provenance"]["pin_witness"]["mode"] = "pinned_capture"
    assert pattern(snapshot, item) != pattern(other, item)

    # A source that goes stale cannot sustain a recurrence or erase the prior attempt.
    before = db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0]
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version='stale' WHERE id="
        "(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
        (fallback["evidence_id"],),
    )
    db.connection.commit()
    assert pin_report(db, "fixture_learner")["source"] is None
    assert db.connection.execute("SELECT count(*) FROM unified_sessions").fetchone()[0] == before

    # A crowded absolute-miss bucket cannot starve relative misses or rehearsals.
    from contextlib import nullcontext
    from types import SimpleNamespace

    import chess_coach.pin_plan_candidates as pin_candidates

    buckets = {}
    next_id = 1000
    for outcome in ("failure", "success"):
        for skill in ("absolute_pin", "relative_pin"):
            count = 25 if (outcome, skill) == ("failure", "absolute_pin") else 2
            rows = []
            for _ in range(count):
                next_id += 1
                rows.append(
                    {
                        "id": next_id,
                        "game_key": str(next_id),
                        "outcome": outcome,
                        "skill": skill,
                        "family": "pin-prevent-mapper",
                    }
                )
            buckets[(outcome, skill)] = rows

    def fake_evidence(_db, _learner, skill, _operation, _before, *, outcome, limit):
        return buckets[(outcome, skill)][:limit], False

    def fake_consider(_db, _learner, row, _sources, cache, _parts, excluded, *_dates):
        if len(cache) >= 20:
            excluded["game replay limit"] += 1
            return None
        cache[row["id"]] = True
        return row

    monkeypatch.setattr(pin_candidates, "evidence", fake_evidence)
    monkeypatch.setattr(pin_candidates, "consider", fake_consider)
    budget = SimpleNamespace(scope=lambda **_kwargs: nullcontext())
    ranked, limited, _ = pin_candidates.candidates(None, "fixture_learner", budget)
    first = ranked[:12]
    assert limited and len(ranked) == 20
    assert {(x["outcome"], x["skill"]) for x in first} == set(buckets)
    relative = [x for x in first if x["skill"] == "relative_pin"]
    selection = select({"matching": [(x, snapshot) for x in relative]})
    assert selection and selection["repeated_miss"]
    successes = [x for x in relative if x["outcome"] == "success"]
    selection = select({"matching": [(x, snapshot) for x in successes]})
    assert selection and not selection["repeated_miss"]
