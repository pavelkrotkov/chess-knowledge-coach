"""Selected-choice coverage, context confounding and private source links."""

import io
import json
import sys

import chess
import chess.engine
import chess.pgn

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.deep_execution_worker import run_deep
from chess_coach.ingest import ingest_pgn
from chess_coach.style_report import style_report
from chess_coach.web import create_app
from tests.test_deep_execution import DeepEngine, options, prepare_selected, use_engine
from tests.test_deep_selection import LEARNER, OPPONENT, PGN


def line(pv, score=0, *, kind="cp", depth=5):
    return {
        "root_move": pv.split()[0],
        "pv": pv,
        "score_kind": kind,
        "score_value": score,
        "score_bound": "exact",
        "depth": depth,
        "status": "limited",
    }


def deep(*lines, status="complete"):
    return {"status": status, "result": {"alternatives": [{"line": item} for item in lines]}}


class FourPlyEngine(DeepEngine):
    def analyse(self, board, limit, multipv, root_moves=None):
        game = chess.pgn.read_game(io.StringIO(PGN))
        assert game is not None
        played = list(game.mainline_moves())[len(board.move_stack)]
        roots = root_moves or [
            played,
            *[m for m in board.legal_moves if m != played][: multipv - 1],
        ]
        values = []
        for move in roots:
            position = board.copy()
            pv = [move]
            position.push(move)
            for _ in range(3):
                next_move = next(iter(position.legal_moves))
                pv.append(next_move)
                position.push(next_move)
            values.append(
                {
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "pv": pv,
                    "nodes": 200,
                    "depth": 5,
                    "time": 0.05,
                }
            )
        return values


def _check_retained_purpose_iterations():
    import asyncio
    import gc
    import threading
    import time
    import warnings
    from types import SimpleNamespace

    from chess_coach.purpose_final import final

    board = chess.Board()
    position = {"id": 1, "uci": "e2e4"}
    first = "e2e4 e7e5 g1f3 b8c6"
    second = "d2d4 d7d5 c1f4 g8f6"

    def info(rank, depth, pv, score=0, nodes=100):
        return {
            "multipv": rank,
            "depth": depth,
            "pv": [chess.Move.from_uci(move) for move in pv.split()],
            "score": chess.engine.PovScore(chess.engine.Cp(score), chess.WHITE),
            "nodes": nodes,
            "time": nodes / 100000,
        }

    class Stream:
        def __init__(self, events):
            self.events = iter(events)
            self.stopped = threading.Event()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.stopped.set()

        def __aiter__(self):
            return self

        async def __anext__(self):
            event = next(self.events, None)
            if event is None:
                raise StopAsyncIteration
            if event == "stall":
                await asyncio.sleep(10)
            if event == "failure":
                raise RuntimeError("synthetic engine failure")
            return event

    class Protocol:
        def __init__(self, loop):
            self.loop, self.events, self.stream = loop, [], None
            self.expected = ["e2e4", "d2d4"]

        async def analysis(self, _board, _limit, *, multipv, root_moves):
            assert multipv == 2 and [move.uci() for move in root_moves] == self.expected
            self.stream = Stream(self.events)
            return self.stream

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    protocol = Protocol(loop)
    engine = SimpleNamespace(protocol=protocol, timeout=0.2)
    try:
        protocol.events = [
            info(1, 4, first),
            info(2, 4, second),
            info(1, 5, second),
            info(2, 5, first),
            info(1, 6, first),
            info(2, 6, "d2d4 d7d5"),
            {"depth": 7, "nodes": 900, "time": 0.09},
        ]
        result, issue = final(engine, board, position, "d2d4", time.monotonic() + 2)
        assert issue is None and result["retained_depth"] == 5
        assert [item["line"]["root_move"] for item in result["lines"]] == ["d2d4", "e2e4"]
        assert result["work"]["nodes"] == 900 and result["work"]["depth"] == 7

        protocol.events = [
            info(1, 4, first),
            info(2, 4, second),
            info(1, 6, first),
            info(2, 6, second, score=200),
        ]
        result, issue = final(engine, board, position, "d2d4", time.monotonic() + 2)
        assert result["retained_depth"] == 6 and issue == "no_similar_alternative"

        bounded = info(1, 4, first)
        bounded["upperbound"] = True
        protocol.events = [bounded, info(2, 4, second)]
        assert (
            final(engine, board, position, "d2d4", time.monotonic() + 2)[1]
            == "no_complete_iteration"
        )
        protocol.events = [info(1, 4, first)]
        assert (
            final(engine, board, position, "d2d4", time.monotonic() + 2)[1]
            == "no_complete_iteration"
        )
        protocol.events = [info(2, 4, second)]
        assert (
            final(engine, board, position, "d2d4", time.monotonic() + 2)[1]
            == "no_complete_iteration"
        )

        protocol.events = [info(1, 4, first), info(1, 4, second), info(2, 4, second)]
        assert (
            final(engine, board, position, "d2d4", time.monotonic() + 2)[1]
            == "no_complete_iteration"
        )

        from chess_coach.opening_experiment import assess as assess_opening
        from chess_coach.opening_measure_search import search as opening_search

        def opening(events, root=board, decision=position):
            protocol.events = events
            return opening_search(engine, root, decision, "d2d4", time.monotonic() + 2)

        protocol.expected = ["e2e4", "d2d4"]
        protocol.events = [
            info(1, 4, first),
            info(2, 4, second),
            info(1, 6, first),
            info(2, 6, "d2d4 d7d5"),
            {"nodes": 190000, "depth": 7, "time": 0.9},
        ]
        measured = opening_search(engine, board, position, "d2d4", time.monotonic() + 2)
        assert measured["status"] == "complete" and measured["retained_depth"] == 4
        assert measured["work"]["nodes"] == 190000 and measured["work"]["depth"] == 7

        exact_three = [info(1, 4, "e2e4 e7e5 g1f3"), info(2, 4, "d2d4 d7d5 c1f4")]
        oversized = info(1, 7, "e2e4 " + "a2a3 " * 100)
        measured = opening([*exact_three, oversized, info(2, 7, second)])
        decision = {"fen": board.fen(), "played_uci": "e2e4"}
        assert measured["retained_depth"] == 4
        assert assess_opening(decision, {"uci": "d2d4"}, measured)[0] is not None

        short = [info(1, 5, "e2e4 e7e5"), info(2, 5, "d2d4 d7d5")]
        measured = opening(short)
        assert measured["status"] == "complete" and measured["retained_depth"] == 5
        assert assess_opening(decision, {"uci": "d2d4"}, measured)[1] == "short_line"

        gap = [
            info(1, 4, first),
            info(2, 4, second),
            info(1, 6, first),
            info(2, 6, second, score=-120),
        ]
        measured = opening(gap)
        assert measured["retained_depth"] == 6
        assert assess_opening(decision, {"uci": "d2d4"}, measured)[1] == "score_gap"
        assert opening([*gap, {"nodes": 200001}])["reason"] == "node_limit_unverified"

        history = chess.Board()
        history.push_uci("g1f3")
        history.push_uci("g8f6")
        protocol.expected = ["f3g1", "d2d4"]
        history_position = {"id": 1, "uci": "f3g1"}
        history_events = [
            info(1, 4, "f3g1 b8c6 b1c3"),
            info(2, 4, "d2d4 d7d5 c1f4"),
            info(1, 6, "f3g1 f6g8 b1c3"),
            info(2, 6, "d2d4 d7d5 c1f4"),
        ]
        assert (
            opening(history_events, history, history_position)["reason"]
            == "incomparable_depth_or_history"
        )
        protocol.expected = ["e2e4", "d2d4"]

        protocol.events = [info(1, 4, first), info(2, 4, second), "failure"]
        assert final(engine, board, position, "d2d4", time.monotonic() + 2)[1] == "engine_failure"

        protocol.events = ["stall"]
        result, issue = final(engine, board, position, "d2d4", time.monotonic() + 0.2)
        assert issue == "worker_deadline"
        assert result["work"] == {
            "nodes": None,
            "depth": None,
            "time_seconds": None,
            "shared_search": True,
            "requested_nodes": 200000,
            "node_limit_exceeded": False,
        }
        assert protocol.stream is not None
        assert protocol.stream.stopped.wait(1)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        engine.protocol = Protocol(loop)
        assert final(engine, board, position, "d2d4", time.monotonic() + 2)[1] == "engine_failure"
        gc.collect()
    assert not any("was never awaited" in str(warning.message) for warning in caught)


def test_profile_uses_owned_current_deep_results_and_private_browser(tmp_path, monkeypatch, capsys):
    _check_retained_purpose_iterations()
    path = tmp_path / "style.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=6)
    use_engine(monkeypatch, FourPlyEngine(db))
    run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=6))
    report = style_report(db, LEARNER)
    assert report["coverage"]["decisions"] == 6
    assert report["selection_counts"]["selected"] == 6
    assert report["selection_counts"]["selection_eligible"] == 6
    assert report["selection_counts"]["selection_capped_out"] == 0
    assert report["selection_counts"]["comparable"] > 0
    item = report["observations"][0]
    assert item["selection_id"] == selection_id and item["analysis_run_id"]
    assert item["played_line"]["root_move"] == item["played_move"]
    assert item["context"]["familiarity"] == "unknown"
    # Control candidates have their own coverage and preserve check-response counts.
    from collections import defaultdict

    from chess_coach import style_center_control, style_purpose_evaluate, style_purpose_view
    from chess_coach.style_counts import counts

    board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    played = line("e4d5 e8d7 e1d2 d7d6")
    other = line("e1d2 e8d7 d2e3 d7d6")
    view = {
        "attempts": [
            {
                "number": 1,
                "final": {
                    "lines": [
                        {"rank": 1, **played},
                        {"rank": 2, **other},
                    ]
                },
            }
        ],
        "limits": {},
    }
    context = {
        "game_id": item["game_id"],
        "position_id": item["position_id"],
        "ply": item["ply"],
        "played_move": "e4d5",
        "pre_move_fen": board.fen(),
        "game_outcome": "unknown",
    }
    slot = {
        "kind": "control",
        "game_id": context["game_id"],
        "position_id": context["position_id"],
        "request_id": 1,
        "sequence": 1,
    }
    snapshot = {"board": board, "position": {"uci": "e4d5"}}

    def state():
        return {
            "views": {},
            "counts": defaultdict(int),
            "observations": [],
            "center_control": {"coverage": defaultdict(int), "seen": set(), "observations": []},
            "early_center": {"coverage": defaultdict(int), "seen": set(), "observations": []},
        }

    original_view = style_purpose_evaluate.current_view
    with monkeypatch.context() as patch:
        patch.setattr(style_purpose_evaluate, "current_view", lambda *args: ("current", view))
        patch.setattr(style_center_control, "current_opening", lambda *args: None)
        patch.setattr(style_center_control, "describe_context", lambda *args: item["context"])
        current = state()
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, snapshot, current, set())
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, snapshot, current, set())
        assert current["counts"]["control_outside_check"] == 2
        assert current["center_control"]["coverage"]["duplicate"] == 1
        center_items = current["center_control"]["observations"]
        assert len(center_items) == 1 and not current["observations"]
        targeted_slot = {**slot, "early_center_target": True}
        targeted = state()
        style_purpose_evaluate.evaluate(
            db, LEARNER, targeted_slot, context, snapshot, targeted, set()
        )
        style_purpose_evaluate.evaluate(
            db, LEARNER, targeted_slot, context, snapshot, targeted, set()
        )
        assert targeted["early_center"]["coverage"]["duplicate"] == 1
        assert targeted["early_center"]["observations"][0]["choice"] == "played_capture"
        assert not targeted["center_control"]["observations"]
        assert center_items[0]["choices"] == {"center_file_opening": "file_opened"}
        dimension = counts(center_items, "center_file_opening")
        assert dimension["opportunities"] == dimension["games"] == 1
        assert not dimension["sufficient"]
        overlap = state()
        style_purpose_evaluate.evaluate(
            db,
            LEARNER,
            slot,
            context,
            snapshot,
            overlap,
            {(slot["game_id"], slot["position_id"])},
        )
        assert overlap["counts"]["control_duplicate"] == 1
        assert overlap["center_control"]["coverage"]["overlap"] == 1
        targeted_overlap = state()
        style_purpose_evaluate.evaluate(
            db,
            LEARNER,
            targeted_slot,
            context,
            snapshot,
            targeted_overlap,
            {(slot["game_id"], slot["position_id"])},
        )
        assert targeted_overlap["early_center"]["coverage"]["ordinary_overlap"] == 1
        assert not overlap["center_control"]["observations"]
        mismatch = state()
        bad_snapshot = {"board": board, "position": {"uci": "e1d2"}}
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, bad_snapshot, mismatch, set())
        assert mismatch["counts"]["control_history_unavailable"] == 1
        assert not mismatch["center_control"]["observations"]
        patch.setattr(style_purpose_evaluate, "current_view", lambda *args: ("stale", None))
        stale = state()
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, snapshot, stale, set())
        assert stale["counts"]["control_stale"] == 1
        targeted_stale = state()
        style_purpose_evaluate.evaluate(
            db, LEARNER, targeted_slot, context, snapshot, targeted_stale, set()
        )
        assert targeted_stale["early_center"]["coverage"]["stale"] == 1
        assert not stale["center_control"]["observations"]
        patch.setattr(style_purpose_evaluate, "current_view", original_view)
        patch.setattr(style_purpose_view, "slot_matches_request", lambda *args: False)
        changed = state()
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, snapshot, changed, set())
        assert changed["counts"]["control_source_unknown"] == 1
        assert not changed["center_control"]["observations"]
        changed_target = state()
        style_purpose_evaluate.evaluate(
            db, LEARNER, targeted_slot, context, snapshot, changed_target, set()
        )
        assert changed_target["early_center"]["coverage"]["unchecked"] == 1
        patch.setattr(style_purpose_evaluate, "current_view", lambda *args: ("current", view))
        view["attempts"][0]["final"]["lines"][1]["depth"] = 3
        shallow = state()
        style_purpose_evaluate.evaluate(db, LEARNER, slot, context, snapshot, shallow, set())
        assert shallow["center_control"]["coverage"]["unavailable"] == 1
        style_purpose_evaluate.evaluate(
            db, LEARNER, targeted_slot, context, snapshot, shallow, set()
        )
        assert shallow["early_center"]["coverage"]["unsupported"] == 1
        assert not shallow["center_control"]["observations"]

    from chess_coach.style_early_center_report import summary as early_summary

    report["early_center"] = early_summary(targeted["early_center"])
    report["center_control"] = {
        **dimension,
        "observations": center_items,
        "coverage": dict(current["center_control"]["coverage"]),
        "scope": "Bounded control candidates.",
    }
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "style-choices", "--learner", LEARNER]
    )
    main()
    output = capsys.readouterr().out
    cli_report = json.loads(output)
    assert cli_report["version"] == "style-choices-v14"
    assert "center_control" in cli_report
    assert "not prior exposure" in cli_report["familiarity_note"]
    assert "overlapping games" in cli_report["trend_note"]
    assert LEARNER not in output and OPPONENT not in output
    assert "game_key" not in output and "fingerprint" not in output
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/style-choices", base_url="https://coach.invalid").status_code == 403
    page = client.get(
        "/style-choices",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
    )
    assert page.status_code == 200 and b"Source choices" in page.data
    assert f"/decisions/{item['position_id']}".encode() in page.data
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_style.style_report", lambda *args, **kwargs: report)
        page = client.get(
            "/style-choices",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "login"},
        )
        assert b"Center-file choices from control comparisons" in page.data
        assert b"Early central pawn choices" in page.data
        assert b"These lines show conditional continuations." in page.data
        assert b"Insufficient data for a direction" in page.data
        assert b"control diagnostic" in page.data


def test_duplicate_imports_do_not_count_as_independent_games(monkeypatch, tmp_path):
    from chess_coach import style_schedule_candidates, style_schedule_control
    from chess_coach.style_early_center_compare import observation as early_observation
    from chess_coach.style_schedule_candidate import candidate

    root = chess.Board()
    root.push_uci("e2e4")
    root.push_uci("d7d5")
    capture = {"uci": "e4d5", "ply": 3, "game_id": 1, "id": 3}
    quiet = {**capture, "uci": "g1f3"}
    assert candidate(capture, root)["early_center"] and candidate(quiet, root)["early_center"]
    assert not candidate({**capture, "ply": 21}, root)["early_center"]

    # The scheduled scout searches only the opposite legal category.
    import time

    from chess_coach import purpose_search
    from chess_coach.purpose_config import EARLY_CENTER
    from chess_coach.purpose_lines import native
    from chess_coach.purpose_view_binding import matches as matches_purpose

    class ScoutEngine:
        def __init__(self):
            self.calls = []

        def analyse(self, board, limit, multipv, root_moves=None):
            self.calls.append((multipv, root_moves))
            assert root_moves and multipv == min(2, len(root_moves))
            return [
                {
                    "pv": [move],
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "depth": 5,
                    "nodes": 100,
                }
                for move in root_moves[:multipv]
            ]

    final_calls = []

    def final(engine, board, position, nominee, deadline):
        final_calls.append((position["uci"], nominee))
        moves = [board.parse_uci(position["uci"]), board.parse_uci(nominee)]
        lines, invalid = native(
            position,
            board,
            [
                {
                    "pv": [move],
                    "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                    "depth": 5,
                    "nodes": 100,
                }
                for move in moves
            ],
        )
        assert not invalid
        return {"lines": lines, "roots": [move.uci() for move in moves]}, None

    with monkeypatch.context() as patch:
        patch.setattr(purpose_search, "final", final)
        for position in (capture, quiet):
            engine = ScoutEngine()
            result, issue = purpose_search.search(
                engine, root, position, time.monotonic() + 10, policy=EARLY_CENTER
            )
            assert issue is None and len(engine.calls) == 1
            assert matches_purpose(
                result, position["uci"], board=root, position=position, policy=EARLY_CENTER
            )
            offered = [move.uci() for move in engine.calls[0][1]]
            if position is quiet:
                assert engine.calls[0][0] == 1 and offered == ["e4d5"]
            else:
                assert "e4d5" not in offered and "g1f3" in offered
                assert matches_purpose(result, position["uci"])
            result["scout"]["lines"][0]["line"]["root_move"] = position["uci"]
            assert not matches_purpose(
                result, position["uci"], board=root, position=position, policy=EARLY_CENTER
            )

        class PartialScout(ScoutEngine):
            def __init__(self, missing):
                super().__init__()
                self.missing = missing

            def analyse(self, *args, **kwargs):
                lines = super().analyse(*args, **kwargs)
                lines[0].pop(self.missing)
                return lines

        for missing in ("pv", "score", "depth"):
            partial, issue = purpose_search.search(
                PartialScout(missing), root, capture, time.monotonic() + 10, policy=EARLY_CENTER
            )
            assert issue is None and partial["scout"]["lines"][0]["rank"] == 2
            assert matches_purpose(
                partial, capture["uci"], board=root, position=capture, policy=EARLY_CENTER
            )
            from copy import deepcopy

            for field, value in (
                ("decision_fen", chess.Board().fen()),
                ("pv", partial["scout"]["lines"][0]["line"]["root_move"] + " a1a8"),
                ("score_value", None),
                ("depth", None),
            ):
                corrupt = deepcopy(partial)
                corrupt["scout"]["lines"][0]["line"][field] = value
                assert not matches_purpose(
                    corrupt, capture["uci"], board=root, position=capture, policy=EARLY_CENTER
                )

        class BoundedScout(ScoutEngine):
            def __init__(self, bound):
                super().__init__()
                self.bound = bound

            def analyse(self, *args, **kwargs):
                lines = super().analyse(*args, **kwargs)
                lines[0][self.bound + "bound"] = True
                return lines

        for bound in ("upper", "lower"):
            bounded, issue = purpose_search.search(
                BoundedScout(bound), root, quiet, time.monotonic() + 10, policy=EARLY_CENTER
            )
            assert issue is None and bounded["scout"]["lines"][0]["line"]["score_bound"] == bound
            assert matches_purpose(
                bounded, quiet["uci"], board=root, position=quiet, policy=EARLY_CENTER
            )
        patch.setattr(purpose_search, "final", lambda *_: ({}, "no_similar_alternative"))
        assert (
            purpose_search.search(
                ScoutEngine(), root, capture, time.monotonic() + 10, policy=EARLY_CENTER
            )[1]
            == "no_similar_alternative"
        )
    assert len(final_calls) == 7
    chosen = candidate(capture, root)
    fallback = {"game_id": 2, "position_id": 4, "early_center": False}
    with monkeypatch.context() as patch:
        patch.setattr(style_schedule_control, "choose", lambda *_: fallback)
        selected, targeted, count = style_schedule_control.control(
            None, "fixture", 1, [chosen, fallback]
        )
        assert selected == chosen and targeted and count == 1
        selected, targeted, _ = style_schedule_control.control(
            None, "fixture", 2, [chosen, fallback]
        )
        assert selected == fallback and not targeted

    # A terminal reserved request must not displace an independent fresh game.
    from collections import defaultdict

    from chess_coach.deep_selection_source import learner_key
    from chess_coach.style_early_center_report import slot_coverage

    fresh_db = Database(":memory:")
    fresh_db.initialize()
    ingest_pgn(fresh_db, PGN)
    ingest_pgn(fresh_db, PGN.replace(OPPONENT, "Independent opponent"))
    positions = [
        [
            row[0]
            for row in fresh_db.connection.execute(
                "SELECT id FROM positions WHERE game_id=? ORDER BY ply LIMIT 2", (game_id,)
            )
        ]
        for game_id in (1, 2)
    ]
    key = learner_key(LEARNER)
    for number, (game_id, position_id) in enumerate(
        ((1, positions[0][0]), (2, positions[1][1])), start=1
    ):
        fresh_db.connection.execute(
            """INSERT INTO purpose_analysis_requests
            (game_id,position_id,learner_key,purpose,policy_version,source_fingerprint,
             config_json,request_fingerprint,status)
            VALUES(?,?,?,'candidate-comparison','candidate-comparison-v1',?,'{}',?,'insufficient')""",
            (game_id, position_id, key, str(number), str(number)),
        )
    fresh_db.connection.execute(
        """INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json)
        VALUES(?,1,'{"early_center_policy":"early-center-v1","early_center_targeted":true}')""",
        (key,),
    )
    fresh_db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
        VALUES(1,'control',1,?,'insufficient','insufficient',1)""",
        (positions[0][0],),
    )
    first = {**chosen, "game_id": 1, "position_id": positions[0][0], "_game_key": "a"}
    second = {**chosen, "game_id": 2, "position_id": positions[1][0], "_game_key": "b"}
    # Ambiguous evidence must not consume the single protection nomination;
    # a success/failure row is only a nomination, not proof of a current source.
    from chess_coach.learner_identity import normalize_identity
    from chess_coach.material_policy import MAPPER
    from chess_coach.style_protection_schedule_budget import resolution_budget
    from chess_coach.style_protection_schedule_discover import discover
    from chess_coach.style_schedule_budget import history_budget

    subject = normalize_identity(LEARNER)
    for position_id, outcome in (
        (first["position_id"], "ambiguous"),
        (second["position_id"], "failure"),
    ):
        run = fresh_db.connection.execute(
            """INSERT INTO mapping_runs
            (producer,position_id,subject,operation,scope_key,mapper_version,input_json,
             input_hash,output_hash,created_at,status)
            VALUES(?,?,?,'prevent','fixture','1','{}',?,'fixture','2026-01-01','active')""",
            (MAPPER, position_id, subject, str(position_id)),
        )
        fresh_db.connection.execute(
            """INSERT INTO evidence_mappings
            (position_id,skill,operation,outcome,confidence,subject,mapping_run_id)
            VALUES(?,'hanging_piece','prevent',?,1,?,?)""",
            (position_id, outcome, subject, run.lastrowid),
        )
    fresh_db.connection.commit()
    with monkeypatch.context() as patch, resolution_budget() as proofs, history_budget() as work:
        patch.setattr(
            "chess_coach.style_protection_schedule_rotation.rank",
            lambda _key, _kind, game, position: (game, position),
        )
        assert discover(fresh_db, LEARNER, key, [first], [], work) == (
            None,
            None,
            "no_evidence_candidate",
            0,
        )
        selected_protection, binding, reason, _ = discover(
            fresh_db, LEARNER, key, [first, second], [], work
        )
        assert (selected_protection, binding, reason) == (
            second,
            None,
            "source_or_proof_unavailable",
        )
        assert proofs["used"] == 1
    identities = {1: "a", 2: "b"}
    selected, targeted, nominated = style_schedule_control.select(
        fresh_db, key, 5, [first, second], None, identities=identities
    )
    assert selected == second and targeted and nominated == 2
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_schedule_fresh_history.reached", lambda: True)
        _selected, deadline_targeted, _nominated = style_schedule_control.select(
            fresh_db, key, 5, [first, second], None, identities=identities
        )
        assert not deadline_targeted
    # Request creation still checks the exact owned source and records only pending work.
    from chess_coach.purpose_request import create as create_purpose

    fresh_db.connection.commit()
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.purpose_request.configuration",
            lambda *_args: (None, {"fixture": "no-engine"}),
        )
        request = create_purpose(fresh_db, second["position_id"], LEARNER)
    assert request["status"] == "pending"
    fresh_db.connection.execute(
        "UPDATE purpose_analysis_requests SET status='complete' WHERE id=?",
        (request["request_id"],),
    )
    selected, targeted, nominated = style_schedule_control.select(
        fresh_db, key, 5, [first, second], None, identities=identities
    )
    assert selected in (first, second) and not targeted and nominated == 2
    coverage = defaultdict(int)
    slot_coverage(
        {"early_center_cycle": True, "early_center_target": False, "early_center_no_fresh": True},
        {},
        coverage,
    )
    assert coverage["fallback"] == coverage["no_fresh"] == 1
    fresh_db.close()

    # An older ordinary job may finish after allocation but before the targeted slot.
    from chess_coach import style_schedule_standard_worker
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.style_schedule_queue import pending as pending_style

    dispatch_db = Database(":memory:")
    dispatch_db.initialize()
    center_pgn = PGN.split("\n\n")[0] + "\n\n1. e4 d5 2. exd5 Qxd5 *"
    ingest_pgn(dispatch_db, center_pgn)
    position = dispatch_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=3"
    ).fetchone()[0]
    for sequence, coverage_json in (
        (0, "{}"),
        (1, '{"early_center_policy":"early-center-v1","early_center_targeted":true}'),
    ):
        cursor = dispatch_db.connection.execute(
            "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
            (key, sequence, coverage_json),
        )
        dispatch_db.connection.execute(
            """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail)
            VALUES(?,'control',1,?,'ready','eligible')""",
            (cursor.lastrowid, position),
        )
    dispatch_db.connection.commit()
    slots = pending_style(dispatch_db, LEARNER)
    assert (
        len(slots) == 2 and not slots[0]["early_center_target"] and slots[1]["early_center_target"]
    )
    from chess_coach.style_schedule_fresh import available as fresh_available

    identity = {1: "a"}
    assert not fresh_available(
        dispatch_db,
        key,
        [{**chosen, "game_id": 1, "position_id": position, "_game_key": "a"}],
        identity,
    )

    def finish_ordinary(db, request_id, *_args, **_kwargs):
        db.connection.execute(
            "UPDATE purpose_analysis_requests SET status='insufficient' WHERE id=?", (request_id,)
        )
        db.connection.commit()
        return {"status": "insufficient", "detail": "fixture"}

    with monkeypatch.context() as patch:

        def stub_configuration(*_args, **kwargs):
            return None, {
                "engine_path": "fixture",
                "fixture": "no-engine",
                "purpose_policy": kwargs.get("policy", "candidate-comparison-v1"),
            }

        patch.setattr("chess_coach.purpose_request.configuration", stub_configuration)
        patch.setattr("chess_coach.purpose_current.configuration", stub_configuration)
        patch.setattr(style_schedule_standard_worker, "run", finish_ordinary)
        config = PipelineConfig(learner=LEARNER)
        ordinary = style_schedule_standard_worker.process_standard(
            dispatch_db, config, slots[0], None
        )
        targeted = style_schedule_standard_worker.process_standard(
            dispatch_db, config, slots[1], None
        )
        reused = style_schedule_standard_worker.process_standard(
            dispatch_db, config, slots[1], None
        )
        from chess_coach.purpose_current import current, owned

        row = owned(dispatch_db, targeted["request_id"], LEARNER)
        _, stored_config = current(dispatch_db, row, LEARNER)
        assert stored_config["purpose_policy"] == EARLY_CENTER
        from chess_coach.purpose_view import show as show_purpose

        assert (
            "opposite central pawn-capture category"
            in show_purpose(dispatch_db, targeted["request_id"], LEARNER)["scope"]
        )
    assert ordinary["status"] == targeted["status"] == "insufficient"
    assert ordinary["request_id"] != targeted["request_id"]
    assert reused["detail"] == "terminal_request_reused" and reused["status"] == "unknown"
    row = dispatch_db.connection.execute(
        "SELECT request_id,status FROM style_schedule_slots WHERE id=?", (slots[1]["id"],)
    ).fetchone()
    assert row["request_id"] == targeted["request_id"] and row["status"] == "unknown"

    assert (
        dispatch_db.connection.execute(
            "SELECT policy_version FROM purpose_analysis_requests WHERE id=?",
            (targeted["request_id"],),
        ).fetchone()[0]
        == EARLY_CENTER
    )
    dispatch_db.close()

    played = line("e4d5 d8d5 b1c3 d5e5")
    alternative = line("g1f3 d5e4 f3g5 e4e3")
    context = {"game_id": 1, "position_id": 3, "ply": 3, "played_move": "e4d5"}
    slot = {"request_id": 1, "sequence": 1}
    view = {
        "attempts": [
            {
                "number": 1,
                "final": {
                    "lines": [
                        {"rank": 1, **played},
                        {"rank": 2, **alternative},
                    ]
                },
            }
        ]
    }
    status, item = early_observation(context, slot, {"board": root}, view)
    assert status == "admitted" and item["choice"] == "played_capture"
    context["played_move"] = "g1f3"
    status, item = early_observation(context, slot, {"board": root}, view)
    assert status == "admitted" and item["choice"] == "alternative_capture"
    view["attempts"][0]["final"]["lines"][0]["depth"] = 3
    assert early_observation(context, slot, {"board": root}, view)[0] == "unsupported"

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    ingest_pgn(db, PGN.replace('Event "Synthetic"', 'Event "Second import"'))
    report = style_report(db, LEARNER)
    assert report["coverage"]["examined_games"] == 2
    assert report["coverage"]["independent_games"] == 1
    assert report["coverage"]["duplicate_games"] == 1
    assert report["coverage"]["familiarity_history_incomplete"]
    assert report["coverage"]["decisions"] == 6
    assert report["coverage"]["outcomes"] == {"unknown": 1}

    # A bounded schedule can prioritize a checked turn only after full replay.
    from chess_coach import style_schedule_nomination, style_schedule_nomination_game
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.style_schedule_budget import history_budget
    from chess_coach.style_schedule_candidates import allocate
    from chess_coach.style_schedule_nomination import prioritize
    from chess_coach.style_schedule_scan import read_games

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, PGN)
    checked = PGN[: PGN.index("1. e4")] + "1. d4 c6 2. e4 Qa5+ 3. Ke2 *\n"
    ingest_pgn(db, checked)
    games = [
        (db.connection.execute("SELECT * FROM games WHERE id=?", (i,)).fetchone(), color)
        for i, color in ((1, "white"), (2, "white"))
    ]
    with history_budget() as budget:
        budget["limit"] = 12
        ordered, coverage = prioritize(db, games, 0)
        assert ordered[0][0]["id"] == 2
        assert coverage["nomination_games"] == 1
        assert coverage["nomination_turns"] == 1
        assert coverage["structural_nomination_games"] == 1
        assert coverage["structural_nomination_turns"] == 1
        assert coverage["structural_nomination_prioritized"]
        candidates, _, _, exhausted, reconstructed = read_games(db, ordered, 0)
        assert reconstructed == 1 and exhausted
        assert any(item["in_check"] and item["status"] == "ready" for item in candidates)
        assert budget["used"] == 12
    with history_budget() as budget:
        budget["limit"] = 12
        coverage, slots, _ = allocate(db, LEARNER, learner_key(LEARNER), 0)
        assert coverage["nomination_games"] == 1
        assert coverage["reconstructed_games"] == 1 and coverage["history_budget_exhausted"]
        assert dict(slots)["target"]["game_id"] == 2
        assert coverage["structural_replayed_positions"] == 1
        assert coverage["structural_target_selected"]
    # A plausible FEN is not proof that the recorded move or game is valid.
    db.connection.execute("UPDATE positions SET uci='a1a1' WHERE game_id=2 AND ply=5")
    ordered, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 1 and ordered[0][0]["id"] == 1
    with history_budget() as budget:
        budget["limit"] = 100
        candidates, skipped, _, _, reconstructed = read_games(db, ordered, 0)
        assert skipped == 1 and reconstructed == 1
        assert not any(item["in_check"] for item in candidates)
    db.connection.execute("UPDATE positions SET uci='e1e2' WHERE game_id=2 AND ply=5")
    after_fen = db.connection.execute(
        "SELECT fen FROM positions WHERE game_id=2 AND ply=5"
    ).fetchone()[0]
    db.connection.execute(
        "UPDATE positions SET fen=(SELECT fen FROM positions WHERE game_id=2 AND ply=4) "
        "WHERE game_id=2 AND ply=5"
    )
    ordered, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 1 and ordered[0][0]["id"] == 1
    db.connection.execute("UPDATE positions SET fen=? WHERE game_id=2 AND ply=5", (after_fen,))
    db.connection.commit()
    forced = PGN.replace('White "fixture_learner"', 'White "fixture_opponent"')
    forced = forced.replace('Black "fixture_opponent"', 'Black "fixture_learner"')
    forced = forced[: forced.index("1. e4")] + "1. e4 f6 2. Qh5+ g6 *\n"
    ingest_pgn(db, forced)
    forced_game = db.connection.execute("SELECT * FROM games WHERE id=3").fetchone()
    ordered, coverage = prioritize(db, [(forced_game, "black"), games[1]], 0)
    assert ordered[0][0]["id"] == 2 and coverage["nomination_games"] == 1
    # Another legal nonforced check has only interpositions: it remains a
    # fallback, while a genuinely different legal response gets priority.
    same = PGN.replace('White "fixture_learner"', 'White "fixture_opponent"')
    same = same.replace('Black "fixture_opponent"', 'Black "fixture_learner"')
    same = same[: same.index("1. e4")] + "1. e4 d5 2. Bb5+ c6 *\n"
    ingest_pgn(db, same)
    same_game = db.connection.execute("SELECT * FROM games WHERE id=4").fetchone()
    ordered, coverage = prioritize(db, [(same_game, "black"), games[1]], 0)
    assert ordered[0][0]["id"] == 2 and coverage["nomination_games"] == 2
    assert coverage["structural_nomination_games"] == 1
    assert coverage["structural_nomination_turns"] == 1
    assert coverage["structural_nomination_prioritized"]
    from chess_coach.style_defense_nomination import distinct
    from chess_coach.style_schedule_game import game_candidates
    from chess_coach.style_schedule_target import target as choose_target

    different_board = chess.Board()
    for san in ("d4", "c6", "e4", "Qa5+"):
        different_board.push_san(san)
    assert distinct(different_board, different_board.parse_san("Ke2")) is True
    capture_board = chess.Board("rnbq1bnr/p2ppkpp/5p2/1pp5/2B1P3/5P1P/PPPP2PR/RNBQK1N1 b Q - 2 7")
    assert capture_board.is_valid() and capture_board.is_check()
    assert distinct(capture_board, capture_board.parse_uci("f7e8")) is True
    from chess_coach.style_defense_evasion import response as defense_response

    assert not defense_response(capture_board, "f7e8")["capture"]
    assert defense_response(capture_board, "b5c4")["capture"]
    same_board = chess.Board()
    for san in ("e4", "d5", "Bb5+"):
        same_board.push_san(san)
    assert distinct(same_board, same_board.parse_san("c6")) is False
    forced_board = chess.Board()
    for san in ("e4", "f6", "Qh5+"):
        forced_board.push_san(san)
    assert distinct(forced_board, forced_board.parse_san("g6")) is False
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_defense_nomination.lines_safe", lambda *_: False)
        assert distinct(different_board, different_board.parse_san("Ke2")) is None
        _, unknown_coverage = prioritize(db, games, 0)
        assert unknown_coverage["structural_nomination_unknown_turns"] == 1
        assert not unknown_coverage["structural_nomination_prioritized"]
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_defense_nomination.MAX_MOVES", 0)
        assert distinct(different_board, different_board.parse_san("Ke2")) is None
    # A qualifying alternate finishing after the worker deadline is not nominated.
    deadline = [False]

    def late_line(*_args):
        deadline[0] = True
        return True

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_defense_nomination.reached", lambda: deadline[0])
        patch.setattr("chess_coach.style_defense_nomination.lines_safe", late_line)
        assert distinct(different_board, different_board.parse_san("Ke2")) is None
    replayed = game_candidates(db, same_game, "black") + game_candidates(db, games[1][0], "white")
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.style_schedule_rotation.rank",
            lambda _key, _kind, game, position: (-game, position),
        )
        chosen, structural, unknown = choose_target(db, learner_key(LEARNER), 0, replayed)
        assert chosen["game_id"] == 2 and structural == 1 and unknown == 0
        fallback_target, _, _ = choose_target(db, learner_key(LEARNER), 1, replayed)
        assert fallback_target["game_id"] == 4
    # In one fully replayed game, choose the structurally distinct later root
    # instead of two earlier same-category check evasions on priority cycles.
    two_checks = PGN[: PGN.index("1. e4")] + (
        "1. Na3 c6 2. d4 Qa5+ 3. b4 Qxb4+ 4. Qd2 a5 5. Qxb4 a4 "
        "6. f3 Ra5 7. Qb6 Rh5 8. Qd8+ Kxd8 9. Kf2 d6 10. Bd2 e5 "
        "11. Kg3 Rh3+ 12. Kf2 *\n"
    )
    ingest_pgn(db, two_checks)
    combined_game = db.connection.execute("SELECT * FROM games WHERE id=5").fetchone()
    same_game_roots = game_candidates(db, combined_game, "white")
    checks = [item for item in same_game_roots if item["in_check"]]
    assert [item["structural_defense"] for item in checks] == [False, False, True]
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.style_schedule_rotation.rank",
            lambda _key, _kind, game, position: (game, position),
        )
        priority_root, count, _ = choose_target(db, learner_key(LEARNER), 0, same_game_roots)
        fallback_root, _, _ = choose_target(db, learner_key(LEARNER), 1, same_game_roots)
    assert count == 1 and priority_root["position_id"] == checks[-1]["position_id"]
    assert fallback_root["position_id"] == checks[0]["position_id"]
    from chess_coach.style_schedule_priority import choose as structural_choice

    qualified = [
        item for item in replayed + same_game_roots if item.get("structural_defense") is True
    ]
    assert {
        structural_choice(learner_key(LEARNER), sequence, qualified)["game_id"]
        for sequence in (0, 2)
    } == {2, 5}
    # Priority cycles do not consume the legacy fallback cursor. With the
    # structural root in the middle hash slot, fallback cycles still visit all
    # three checked roots rather than repeating that same slot forever.
    from chess_coach import style_schedule_store

    ranked = {
        checks[0]["position_id"]: 0,
        checks[-1]["position_id"]: 1,
        checks[1]["position_id"]: 2,
    }

    def fixed_rank(_key, _kind, game, position):
        return (game, ranked.get(position, 0))

    control = game_candidates(db, games[0][0], "white")[0]

    def cycle_allocation(database, _learner, key, sequence):
        selected, count, _unknown = choose_target(database, key, sequence, same_game_roots)
        structural = bool(sequence % 2 == 0 and count and selected)
        return (
            {"structural_target_selected": structural},
            (("target", selected), ("control", control)),
            same_game_roots,
        )

    positions = []
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.style_schedule_rotation.rank", fixed_rank)
        patch.setattr(style_schedule_store, "allocate", cycle_allocation)
        patch.setattr(
            style_schedule_store, "discover", lambda *_args: (None, None, "unavailable", 0)
        )
        patch.setattr(style_schedule_store, "insert_protection", lambda *_args: None)
        for _ in range(6):
            with history_budget():
                cycle = style_schedule_store.create_cycle(db, LEARNER)
            positions.append(
                db.connection.execute(
                    "SELECT position_id FROM style_schedule_slots WHERE cycle_id=? AND kind=?",
                    (cycle, "target"),
                ).fetchone()[0]
            )
    cursor_rows = dict(
        db.connection.execute(
            "SELECT kind,next_index FROM style_schedule_rotation WHERE learner_key=? AND game_id IN (?,?)",
            (learner_key(LEARNER), combined_game["id"], control["game_id"]),
        ).fetchall()
    )
    assert cursor_rows == {"target": 3, "control": 6}

    # A targeted control uses the durable cycle sequence without advancing
    # the ordinary-control rotation cursor.
    def center_cycle(*_args):
        return (
            {"early_center_policy": "early-center-v1", "early_center_targeted": True},
            (("target", None), ("control", control)),
            [control],
        )

    with monkeypatch.context() as patch:
        patch.setattr(style_schedule_store, "allocate", center_cycle)
        patch.setattr(style_schedule_store, "next_sequence", lambda *_: (learner_key(LEARNER), 9))
        patch.setattr(
            style_schedule_store, "discover", lambda *_args: (None, None, "unavailable", 0)
        )
        patch.setattr(style_schedule_store, "insert_protection", lambda *_args: None)
        with history_budget():
            center_id = style_schedule_store.create_cycle(db, LEARNER)
    from chess_coach.style_purpose_slots import slots as purpose_slots

    persisted, _ = purpose_slots(db, LEARNER)
    assert next(
        row for row in persisted if row["cycle_id"] == center_id and row["kind"] == "control"
    )["early_center_target"]
    assert (
        db.connection.execute(
            "SELECT next_index FROM style_schedule_rotation WHERE learner_key=? AND game_id=? AND kind='control'",
            (learner_key(LEARNER), control["game_id"]),
        ).fetchone()[0]
        == 6
    )
    assert positions[::2] == [checks[-1]["position_id"]] * 3
    assert positions[1::2] == [
        checks[0]["position_id"],
        checks[-1]["position_id"],
        checks[1]["position_id"],
    ]
    fallback, coverage = prioritize(db, games, 1)
    assert fallback[0][0]["id"] == 1 and not coverage["nomination_prioritized"]
    fallback, _ = prioritize(db, games, 3)
    assert fallback[0][0]["id"] == 2
    db.connection.execute("DELETE FROM positions WHERE game_id=2 AND ply=4")
    ordered, coverage = prioritize(db, games, 0)
    assert ordered[0][0]["id"] == 1 and coverage["nomination_unknown_games"] == 1
    assert coverage["nomination_games"] == 0
    # A deadline during a game leaves that game and the rest unchecked.
    calls = iter((False, True, True))
    with monkeypatch.context() as patch:
        patch.setattr(style_schedule_nomination, "reached", lambda: next(calls))
        patch.setattr(style_schedule_nomination_game, "reached", lambda: next(calls))
        _, coverage = prioritize(db, games, 0)
    assert coverage["nomination_unknown_games"] == 0
    assert coverage["nomination_unchecked_games"] == 2
    db.close()

    # A 500-unit scan can replay only one 130-ply game. Reserved starts
    # must nevertheless visit both games rather than only even offsets.
    rotation_db = Database(":memory:")
    rotation_db.initialize()
    for label, prefix in (
        ("ordinary", ["e2e4", "e7e5"]),
        ("center", ["e2e4", "d7d5", "e4d5", "d8d5"]),
    ):
        game = chess.pgn.Game()
        game.headers.update(
            {
                "Event": label,
                "White": LEARNER,
                "Black": OPPONENT,
                "Result": "*",
                "UTCDate": "2026.01.01",
                "UTCTime": "00:00:00",
            }
        )
        board = game.board()
        node = game
        moves = prefix + ["g1f3", "g8f6", "f3g1", "f6g8"] * 33
        for text in moves[:130]:
            move = board.parse_uci(text)
            node = node.add_variation(move)
            board.push(move)
        ingest_pgn(rotation_db, str(game))
    rotation_games = [
        (rotation_db.connection.execute("SELECT * FROM games WHERE id=?", (i,)).fetchone(), "white")
        for i in (1, 2)
    ]
    for sequence, expected in ((1, 1), (5, 2), (9, 1), (13, 2)):
        with history_budget() as budget:
            budget["limit"] = 500
            ordered, _ = prioritize(rotation_db, rotation_games, sequence)
            nominated, _, _, exhausted, replayed = read_games(rotation_db, ordered, 0)
            assert ordered[0][0]["id"] == expected and replayed == 1 and exhausted
            assert budget["used"] == 500
            assert any(item["early_center"] for item in nominated) == (expected == 2)

    # The bounded advisory pass can put a feasible check/center pair ahead of a
    # long unrelated game. Full replay remains the source of both slots.
    game = chess.pgn.Game()
    game.headers.update(
        {
            "Event": "independent check",
            "White": LEARNER,
            "Black": OPPONENT,
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "00:00:01",
        }
    )
    board = game.board()
    node = game
    moves = ["d2d4", "c7c6", "e2e4", "d8a5", "e1e2"]
    moves += ["g8f6", "g1f3", "f6g8", "f3g1"] * 14
    for text in moves[:60]:
        move = board.parse_uci(text)
        node = node.add_variation(move)
        board.push(move)
    ingest_pgn(rotation_db, str(game))
    check_game = rotation_db.connection.execute("SELECT * FROM games WHERE id=3").fetchone()
    paired_games = [*rotation_games, (check_game, "white")]
    for sequence in (1, 5):
        with monkeypatch.context() as patch:
            patch.setattr(
                style_schedule_candidates,
                "recent_games",
                lambda *_args, **_kwargs: (paired_games, {"game_limit_reached": False}),
            )
            with history_budget() as budget:
                budget["limit"] = 500
                coverage, slots, replayed = allocate(rotation_db, LEARNER, "key", sequence)
                assert coverage["early_center_nomination_prioritized"]
                assert coverage["early_center_nomination_games"] >= 1
                assert coverage["reconstructed_games"] == 2 and budget["used"] <= 500
                target, control = slots[0][1], slots[1][1]
                assert target["game_id"] == 3 and target["in_check"]
                assert control["game_id"] == 2 and control["early_center"]
                assert target["game_id"] != control["game_id"] and replayed
    with history_budget() as budget:
        budget["limit"] = 350
        fallback, coverage = prioritize(rotation_db, paired_games, 1)
        assert fallback[0][0]["id"] == 1
        assert not coverage["early_center_nomination_prioritized"]
    unchanged, coverage = prioritize(rotation_db, paired_games, 3)
    assert unchanged[0][0]["id"] == 2
    assert not coverage["early_center_nomination_prioritized"]
    # No checked target is needed to keep a verified early control available.
    with monkeypatch.context() as patch:
        patch.setattr(
            style_schedule_candidates,
            "recent_games",
            lambda *_args, **_kwargs: (
                list(reversed(rotation_games)),
                {"game_limit_reached": False},
            ),
        )
        with history_budget() as budget:
            budget["limit"] = 500
            coverage, slots, _ = allocate(rotation_db, LEARNER, "key", 1)
            assert slots[0][1] is None and slots[1][1]["early_center"]
            assert coverage["early_center_targeted"]
        patch.setattr(style_schedule_nomination_game, "identity", lambda *_args: None)
        with history_budget() as budget:
            budget["limit"] = 500
            coverage, slots, _ = allocate(rotation_db, LEARNER, "key", 1)
            assert slots[1][1] is not None and not coverage["early_center_targeted"]

    # When a center game also has a checked turn, a distinct checked target
    # keeps the independently replayed center candidate available for control.
    from chess_coach import style_schedule_target

    center = {
        "game_id": 2,
        "position_id": 1,
        "early_center": True,
        "in_check": False,
        "status": "ready",
        "structural_defense": None,
    }
    own_check = {**center, "position_id": 2, "early_center": False, "in_check": True}
    separate_check = {**own_check, "game_id": 3}
    with monkeypatch.context() as patch:
        patch.setattr(style_schedule_target, "choose", lambda _db, _key, _kind, rows: rows[0])
        target, _, _ = style_schedule_target.target(
            rotation_db, "key", 1, [center, own_check, separate_check]
        )
        assert target["game_id"] == 3
        unknown_check = {**separate_check, "status": "unknown"}
        target, _, _ = style_schedule_target.target(
            rotation_db, "key", 1, [center, own_check, unknown_check]
        )
        assert target["game_id"] == 2
        known_center = {**center, "_game_key": "a"}
        second_center = {**center, "game_id": 3, "_game_key": "b"}
        unknown_check = {**own_check, "game_id": 4, "_game_key": None}
        known_check = {**own_check, "_game_key": "a"}
        targets = [unknown_check, known_check, known_center, second_center]
        target, _, _ = style_schedule_target.target(rotation_db, "key", 1, targets)
        assert target["game_id"] == 2
        target, _, _ = style_schedule_target.target(
            rotation_db, "key", 1, [unknown_check, known_center, second_center]
        )
        assert target["game_id"] == 4
        target, _, _ = style_schedule_target.target(rotation_db, "key", 3, targets)
        assert target["game_id"] == 4
    rotation_db.close()

    # Cosmetic reimports are one game even when each contains both an early
    # center choice and a checked turn. The independent check still fits.
    duplicate_db = Database(":memory:")
    duplicate_db.initialize()

    def padded_game(event, prefix, length=120):
        game = chess.pgn.Game()
        game.headers.update(
            {
                "Event": event,
                "White": LEARNER,
                "Black": OPPONENT,
                "Result": "*",
                "UTCDate": "2026.01.01",
                "UTCTime": "00:00:00",
            }
        )
        board, node = game.board(), game
        moves = prefix + ["g8f6", "g1f3", "f6g8", "f3g1"] * 34
        for text in moves[:length]:
            move = board.parse_uci(text)
            node = node.add_variation(move)
            board.push(move)
        return str(game)

    both = padded_game(
        "original",
        [
            "e2e4",
            "d7d5",
            "e4d5",
            "d8d5",
            "b1c3",
            "d5e5",
            "f1e2",
        ],
    )
    duplicate = both.replace('[Event "original"]', '[Event "cosmetic copy"]')
    duplicate = duplicate.replace('[Site "?"]', '[Site "https://example.invalid/copy"]')
    duplicate = duplicate.replace("1. e4", "1. e4 {comment} ", 1)
    same_context = padded_game("same context", ["d2d4", "c7c6", "e2e4", "d8a5", "e1e2"])
    separate = same_context.replace(OPPONENT, "independent_opponent")
    for pgn in (both, duplicate, separate, same_context):
        ingest_pgn(duplicate_db, pgn)
    duplicate_games = [
        (
            duplicate_db.connection.execute("SELECT * FROM games WHERE id=?", (i,)).fetchone(),
            "white",
        )
        for i in (1, 2, 3)
    ]
    from chess_coach.mastery_game_lookup import decisions_for_game

    identities = {}
    with history_budget() as budget:
        budget["limit"] = 500
        prioritize(duplicate_db, duplicate_games, 1, identities=identities)
    verified = decisions_for_game(duplicate_db, 1, LEARNER)
    assert verified and identities[1] == next(iter(verified.values()))["game_key"]
    assert identities[1] == identities[2] != identities[3]
    # The original import can leave the recent ten while a cosmetic alias remains.
    duplicate_key = learner_key(LEARNER)
    duplicate_db.connection.execute(
        """INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json)
        VALUES(?,1,'{"early_center_policy":"early-center-v1","early_center_targeted":true}')""",
        (duplicate_key,),
    )
    old_position = duplicate_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    duplicate_db.connection.execute(
        """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail)
        VALUES(1,'control',1,?,'ready','eligible')""",
        (old_position,),
    )
    alias_position = duplicate_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    independent_position = duplicate_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=3 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    from chess_coach.style_schedule_fresh import available as fresh_available

    alias = {"game_id": 2, "position_id": alias_position, "_game_key": identities[2]}
    independent = {"game_id": 3, "position_id": independent_position, "_game_key": identities[3]}
    same_game = duplicate_db.connection.execute("SELECT * FROM games WHERE id=4").fetchone()
    same_key = style_schedule_nomination_game.inspect(
        duplicate_db, same_game, "white", center=True
    )[-1]
    same_position = duplicate_db.connection.execute(
        "SELECT id FROM positions WHERE game_id=4 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    same = {"game_id": 4, "position_id": same_position, "_game_key": same_key}
    assert same_key not in (identities[2], identities[3])
    candidates, keys = [alias, independent, same], {2: identities[2], 3: identities[3], 4: same_key}
    with history_budget() as budget:
        budget["limit"] = 500
        assert fresh_available(duplicate_db, duplicate_key, candidates, keys) == [independent]
        assert budget["used"] == 0
    duplicate_db.connection.execute("SAVEPOINT contradictory_prior")
    duplicate_db.connection.execute("UPDATE positions SET uci='d2d4' WHERE game_id=1 AND ply=1")
    assert decisions_for_game(duplicate_db, 1, LEARNER) is None
    assert fresh_available(duplicate_db, duplicate_key, candidates, keys) == [independent]
    duplicate_db.connection.execute("ROLLBACK TO contradictory_prior")
    duplicate_db.connection.execute("RELEASE contradictory_prior")
    with monkeypatch.context() as patch:
        patch.setattr(
            style_schedule_candidates,
            "recent_games",
            lambda *_args, **_kwargs: (duplicate_games, {"game_limit_reached": False}),
        )
        with history_budget() as budget:
            budget["limit"] = 500
            coverage, slots, replayed = allocate(duplicate_db, LEARNER, "key", 1)
            assert coverage["early_center_nomination_prioritized"]
            assert coverage["reconstructed_games"] == 2 and coverage["duplicate_games"] == 1
            assert budget["used"] == 480 and replayed
            target, control = slots[0][1], slots[1][1]
            assert target["game_id"] == 3 and control["game_id"] == 1
            assert target["_game_key"] != control["_game_key"] and control["early_center"]
    with history_budget() as budget:
        budget["limit"] = 500
        _items, _skipped, duplicates, exhausted, reconstructed = read_games(
            duplicate_db, duplicate_games, 0
        )
        assert duplicates == 0 and reconstructed == 2 and exhausted and budget["used"] == 500
    duplicate_db.close()

    # Reuse only the verified in-process boards, so both jobs fit the old 2,000-unit cap.
    from contextlib import nullcontext

    from chess_coach import purpose_worker
    from chess_coach.purpose_request import create as request_purpose

    budget_db = Database(":memory:")
    budget_db.initialize()
    prefix = ["e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d5e5", "f1e2"]
    for size in (135, 18):
        ingest_pgn(budget_db, padded_game(f"budget-{size}", prefix, size))
    decisions = [
        budget_db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=3", (game_id,)
        ).fetchone()[0]
        for game_id in (1, 2)
    ]

    def configuration(*_args, **kwargs):
        return None, {
            "engine_path": "fixture",
            "purpose_policy": kwargs.get("policy", "candidate-comparison-v1"),
        }

    def execute(_db, snapshot, _config, _deadline):
        snapshot["board"].push(next(iter(snapshot["board"].legal_moves)))
        return "complete", "comparable", {}

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.purpose_request.configuration", configuration)
        patch.setattr("chess_coach.purpose_current.configuration", configuration)
        patch.setattr(purpose_worker, "deep_lock", lambda *_: nullcontext())
        patch.setattr(purpose_worker, "execute", execute)
        with history_budget() as budget:
            budget["used"] = 888
            target = request_purpose(budget_db, decisions[0], LEARNER)
            assert (
                purpose_worker.run(budget_db, target["request_id"], LEARNER)["status"] == "complete"
            )
            assert budget["used"] == 1428
            control = request_purpose(budget_db, decisions[1], LEARNER, policy=EARLY_CENTER)
            assert (
                purpose_worker.run(budget_db, control["request_id"], LEARNER)["status"]
                == "complete"
            )
            assert budget["used"] == 1500

        first = budget_db.connection.execute(
            "SELECT id FROM positions WHERE game_id=2 AND ply=1"
        ).fetchone()[0]
        stale = request_purpose(budget_db, first, LEARNER)

        def changed(db, _snapshot, _config, _deadline):
            db.connection.execute("UPDATE positions SET uci='d2d4' WHERE game_id=2 AND ply=1")
            db.connection.commit()
            return "complete", "comparable", {}

        patch.setattr(purpose_worker, "execute", changed)
        assert purpose_worker.run(budget_db, stale["request_id"], LEARNER)["status"] == "stale"

        def changed_during_create(db, _snapshot, _engine_path, policy):
            db.connection.execute("UPDATE positions SET uci='d2d4' WHERE game_id=1 AND ply=1")
            db.connection.commit()
            return configuration(policy=policy)[1]

        patch.setattr("chess_coach.purpose_request.configured", changed_during_create)
        import pytest

        with pytest.raises(ValueError, match="verified source changed"):
            request_purpose(budget_db, decisions[0], LEARNER)
    budget_db.close()
    _opening_fit_route(monkeypatch, tmp_path)


def test_report_engine_digest_reuse_and_freshness(tmp_path, monkeypatch):
    import hashlib
    import os
    from pathlib import Path

    import pytest

    import chess_coach.engine_report_cache as digest_cache
    import chess_coach.style_report as report_module
    from chess_coach.analysis_configuration import engine_config

    binary = tmp_path / "engine"
    binary.write_bytes(b"first")
    binary.chmod(0o700)
    db = Database(":memory:")
    db.initialize()
    real_digest = hashlib.file_digest
    hashed = []

    def counted(file, algorithm):
        hashed.append(True)
        return real_digest(file, algorithm)

    def configure():
        return engine_config(binary, 100, None, None, 2, 1, 16, {})["engine_sha256"]

    real_open = Path.open
    denied = False

    def open_checked(path, *args, **kwargs):
        if denied and path == binary:
            raise PermissionError("synthetic unavailable engine")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(digest_cache.hashlib, "file_digest", counted)
    monkeypatch.setattr(Path, "open", open_checked)

    def exercise(_db, _learner, *, max_games):
        nonlocal denied
        first = configure()
        assert configure() == first and len(hashed) == 1
        previous = binary.stat()
        binary.write_bytes(b"other")
        os.utime(binary, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        changed = configure()
        assert changed != first and len(hashed) == 2
        replacement = tmp_path / "replacement"
        replacement.write_bytes(b"third")
        replacement.chmod(0o700)
        replacement.replace(binary)
        assert configure() != changed and len(hashed) == 3
        denied = True
        with pytest.raises(PermissionError):
            configure()
        denied = False
        binary.write_bytes(b"forth")
        real_hash = digest_cache._digest

        def changing(file):
            value = real_hash(file)
            binary.write_bytes(b"final")
            return value

        with monkeypatch.context() as patch:
            patch.setattr(digest_cache, "_digest", changing)
            with pytest.raises(OSError, match="changed"):
                configure()
        assert configure() != changed and len(hashed) == 5
        binary.write_bytes(b"before")
        new_binary = tmp_path / "new-engine"
        new_binary.write_bytes(b"after")
        new_binary.chmod(0o700)

        def replacing(file):
            value = real_hash(file)
            new_binary.replace(binary)
            return value

        with monkeypatch.context() as patch:
            patch.setattr(digest_cache, "_digest", replacing)
            with pytest.raises(OSError, match="changed"):
                configure()
        configure()
        assert len(hashed) == 7
        return {"max_games": max_games}

    monkeypatch.setattr(report_module, "_style_report", exercise)
    assert report_module.style_report(db, LEARNER, max_games=1) == {"max_games": 1}
    configure()
    configure()
    assert len(hashed) == 9
    db.close()


def _opening_fit_route(monkeypatch, tmp_path):
    """A normal choices request admits current owned evidence and public windows in memory."""
    import html
    import re
    import sqlite3
    import time
    from contextlib import nullcontext
    from pathlib import Path

    import pytest

    import chess_coach.opening_course_public as coursepublic
    import chess_coach.opening_profile_lookup as lookup
    import chess_coach.opening_profile_read as profile_read
    import chess_coach.opening_unfamiliar_guard as guard
    import chess_coach.opening_unfamiliar_public as unpublic
    import chess_coach.web_unfamiliar_course as course_web
    import chess_coach.web_unfamiliar_measure as web
    from chess_coach import purpose_worker
    from chess_coach.deep_selection_source import learner_key
    from chess_coach.opening_fit_owned import _game
    from chess_coach.opening_fit_owned_summary import summarize
    from chess_coach.opening_profile_index import INDEX_NAME
    from chess_coach.opening_snapshot import import_snapshot
    from chess_coach.opening_storage import position_key
    from chess_coach.opening_unfamiliar_course import preview as course_preview
    from chess_coach.purpose_lines import native
    from chess_coach.purpose_request import create

    real_course_planning = coursepublic.planning
    real_course_identity = coursepublic._identity
    real_course_private = coursepublic._private_file
    owned = Database(":memory:")
    owned.initialize()
    import_snapshot(owned)
    real_connect = sqlite3.connect
    public = real_connect("file:opening-fit-test?mode=memory&cache=shared", uri=True)
    public.executescript(
        "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
        "CREATE TABLE games(id INTEGER PRIMARY KEY,context TEXT NOT NULL,site TEXT NOT NULL,"
        "total_plies INTEGER NOT NULL);"
        "CREATE TABLE moves(game_id INTEGER,ply INTEGER,parent TEXT,san TEXT,uci TEXT,"
        "shapes TEXT,PRIMARY KEY(game_id,ply));"
        "CREATE INDEX profile_edge ON moves(parent,uci,game_id,ply);"
    )
    metadata = {
        "source_sha256": lookup.SOURCE_SHA256,
        "source_url": lookup.SOURCE,
        "source_archive": lookup.SOURCE_ARCHIVE,
        "source_month": lookup.SOURCE_MONTH,
        "license": lookup.LICENSE,
        "license_url": lookup.LICENSE_URL,
        "transform": lookup.TRANSFORM,
        "opening_graph": lookup.GRAPH_SHA256,
        "opening_version": lookup.VERSION,
        "structure_version": lookup.STRUCTURE_VERSION,
        "parent_plies": lookup.PARENT_PLIES,
        "window_plies": lookup.WINDOW_PLIES,
        "stored_plies": lookup.STORED_PLIES,
        "coverage": {
            "accepted": 20,
            "examined": 20,
            "excluded": 0,
            "duplicates": 0,
            "unknown_context": 0,
            "truncated": False,
        },
    }
    public.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        [(key, json.dumps(value)) for key, value in metadata.items()],
    )
    low = "e3 e6 Nf3 Nf6 Be2 Be7 O-O O-O d3 d6 b3 b6 Bb2 Bb7 Nbd2 Nbd7 Re1 Re8 Bf1 Bf8"
    high = "Nf3 d5 e4 Nf6 d3 e6 Be2 Be7 O-O O-O Nbd2 Nbd7 Re1 Re8 b3 b6 Bb2 Bb7 Bf1 Bf8"
    for index in range(20):
        board = chess.Board()
        rows = []
        for ply, text in enumerate((low if index < 10 else high).split(), 1):
            move = board.parse_san(text)
            rows.append((index + 1, ply, position_key(board), board.san(move), move.uci(), "[]"))
            board.push(move)
        context = {
            "Date": "2026.09.01",
            "White": str(index),
            "Black": str(index + 20),
            "Event": "fixture",
            "Result": "1-0",
        }
        public.execute(
            "INSERT INTO games VALUES (?,?,?,?)", (index + 1, json.dumps(context), "", 20)
        )
        public.executemany("INSERT INTO moves VALUES (?,?,?,?,?,?)", rows)
    public.commit()

    def execute(_db, snapshot, _config, _deadline):
        board, position = snapshot["board"], snapshot["position"]
        pvs = ("e4d5 d8d5 b1c3 d5e5", "g1f3 d5e4 f3g5 e4e3")
        raw = [
            {
                "pv": [chess.Move.from_uci(move) for move in line.split()],
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "nodes": 500,
                "depth": 5,
                "time": 0.05,
            }
            for line in pvs
        ]
        lines, invalid = native(position, board, raw)
        assert not invalid
        result = {
            "scout": {"lines": lines},
            "final": {"lines": lines, "roots": ["e4d5", "g1f3"]},
            "engine": {},
            "runtime_engine": {},
        }
        return "complete", "comparable", result

    try:
        with monkeypatch.context() as patch:
            patch.setattr(purpose_worker, "deep_lock", lambda *_: nullcontext())
            patch.setattr(purpose_worker, "execute", execute)
            for index in range(3):
                pgn = (
                    f'[Event "Fixture"]\n[White "learner"]\n[Black "opponent{index}"]\n'
                    f'[UTCDate "2026.01.01"]\n[UTCTime "12:00:0{index}"]\n'
                    '[TimeControl "600+0"]\n[Result "*"]\n\n'
                    "1. e4 d5 2. exd5 Qxd5 3. Nc3 Qe5+ *\n"
                )
                ingest_pgn(owned, pgn)
                position = owned.connection.execute(
                    "SELECT id FROM positions WHERE game_id=? AND ply=3", (index + 1,)
                ).fetchone()[0]
                request_id = create(owned, position, "learner", engine_path=sys.executable)[
                    "request_id"
                ]
                assert purpose_worker.run(owned, request_id, "learner")["status"] == "complete"
                cycle = owned.connection.execute(
                    "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
                    (
                        learner_key("learner"),
                        1 + 4 * index,
                        json.dumps(
                            {
                                "early_center_policy": "early-center-v1",
                                "early_center_targeted": True,
                            }
                        ),
                    ),
                ).lastrowid
                owned.connection.execute(
                    """INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id)
                    VALUES(?,'control',?,?,'complete','fixture',?)""",
                    (cycle, index + 1, position, request_id),
                )
                owned.connection.commit()

            def connect(path, *args, **kwargs):
                if INDEX_NAME in str(path):
                    return real_connect("file:opening-fit-test?mode=memory&cache=shared", uri=True)
                return real_connect(path, *args, **kwargs)

            patch.setattr(sqlite3, "connect", connect)
            fake_path, identity = Path("/synthetic") / INDEX_NAME, (1, 2, 3, 4, 5)
            patch.setattr(guard, "_index", lambda *_: (fake_path, identity))
            for module in (unpublic, coursepublic, profile_read):
                patch.setattr(module, "planning", lambda *_: (fake_path.parent, None))
                patch.setattr(module, "_private_file", lambda *_: True)
            for module in (unpublic, coursepublic):
                patch.setattr(module, "_identity", lambda *_: identity)
            patch.setattr(web, "database", lambda: owned)
            patch.setattr(course_web, "database", lambda: owned)
            patch.setattr("chess_coach.web_tactical_exposure.database", lambda: owned)
            app = create_app(
                db_path=":memory:",
                subject="learner",
                actor="fixture",
                corpus="test",
                login="fixture",
                origin="https://coach.invalid",
                project_root="/synthetic",
            )
            client = app.test_client()
            headers = {"Tailscale-User-Login": "fixture"}
            url = "/repertoire/unfamiliar?choices=1"
            version = course_preview(owned, "/synthetic", "learner")["version"]
            before = (owned.connection.total_changes, public.total_changes)
            protected = (
                "unified_sessions",
                "puzzle_sessions",
                "evidence_mappings",
                "training_items",
                "training_attempts",
            )
            snapshots = {
                table: [tuple(row) for row in owned.connection.execute(f"SELECT * FROM {table}")]
                for table in protected
            }
            page = client.get(url, base_url="https://coach.invalid", headers=headers)
            text = page.get_data(as_text=True)
            assert page.status_code == 200 and text.count("Learning opportunity fit") == 1
            assert "10 of 10 complete legal 20-ply games" in text
            assert "0 of 10 complete legal 20-ply games" in text
            assert "Public availability counts positions" in text and "time control" in text
            assert "<summary>How the center-choice check works</summary>" in text
            assert "Exploratory because a different covered branch" in text
            match = re.search(r'<a href="([^"]+)">Learning opportunity fit:', text)
            assert match and "move=g1f3" in html.unescape(match.group(1))
            selected = client.get(
                html.unescape(match.group(1)), base_url="https://coach.invalid", headers=headers
            )
            assert selected.status_code == 200 and b"Play White" in selected.data
            assert course_preview(owned, "/synthetic", "learner")["version"] == version
            assert owned.connection.total_changes > before[0] and public.total_changes == before[1]
            recorded = owned.connection.execute(
                "SELECT prompt_key FROM tactical_exposures WHERE subject=? AND kind='served' LIMIT 1",
                ("learner",),
            ).fetchone()
            assert recorded is not None
            from chess_coach.tactical_exposure_check import check as exposure_check

            assert exposure_check(owned, "learner", recorded[0]) == "provided"
            assert exposure_check(owned, "other", recorded[0]) == "not_recorded"
            assert {
                table: [tuple(row) for row in owned.connection.execute(f"SELECT * FROM {table}")]
                for table in protected
            } == snapshots

            # A cooperative expiry during actual PGN replay leaves the choices
            # available and lets the final source guard complete.
            import chess_coach.style_schedule_budget as schedule_budget

            with patch.context() as expired:
                expired.setattr(
                    schedule_budget, "reached", lambda: schedule_budget.DEADLINE.get() is not None
                )
                timed = client.get(url, base_url="https://coach.invalid", headers=headers)
            assert timed.status_code == 200 and b"All choices remain exploratory" in timed.data
            assert b"Learning opportunity fit" not in timed.data
            assert course_preview(owned, "/synthetic", "learner")["version"] == version

            # With no possible owned quorum, the costly style replay is skipped,
            # but checked public branch availability is still visible.
            import chess_coach.opening_fit_owned as fit_owned

            with patch.context() as sparse:
                sparse.setattr(
                    fit_owned,
                    "_relevant",
                    lambda *_: (
                        {"targeted": 0, "completed": 0, "unchecked": 0, "possible_games": 0},
                        {},
                    ),
                )
                sparse.setattr(
                    fit_owned,
                    "style_report",
                    lambda *_, **_k: pytest.fail("unnecessary style scan"),
                )
                sparse_page = client.get(url, base_url="https://coach.invalid", headers=headers)
            assert b"Learning opportunity fit" not in sparse_page.data
            assert b"10 of 10 complete legal 20-ply games" in sparse_page.data

            # Black first-turn context uses the opponent's exact UCI move.
            black = (
                '[Event "Black"]\n[White "opponent"]\n[Black "learner"]\n'
                '[UTCDate "2026.01.01"]\n[UTCTime "12:00:04"]\n'
                '[TimeControl "600+0"]\n[Result "*"]\n\n1. e4 e6 *\n'
            )
            ingest_pgn(owned, black)
            black_id = owned.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
            assert _game(owned, "learner", {"game_id": black_id}, "e2e4")[0] == "black"
            assert _game(owned, "learner", {"game_id": black_id}, "d2d4") is None

            # A changed original history removes that game from current owned evidence.
            owned.connection.execute(
                "UPDATE positions SET fen=fen || ' ' WHERE game_id=1 AND ply=3"
            )
            owned.connection.commit()
            stale = client.get(url, base_url="https://coach.invalid", headers=headers)
            assert stale.status_code == 200 and b"Learning opportunity fit" not in stale.data
            assert b"complete legal 20-ply games" in stale.data
            assert b"Exploratory because the owned choice evidence does not qualify" in stale.data

            rows = [
                {
                    "id": index,
                    "choice": "played_capture",
                    "date": f"2026-01-01T00:00:0{index}+00:00",
                    "time_control": "600+0",
                }
                for index in range(3)
            ]
            assert summarize(rows)["positive"]
            assert not summarize([{**row, "time_control": None} for row in rows])["positive"]
            for malformed in ("UNKNOWN", "nonsense", "0+0", "0600+0", "600+-1", "600+00"):
                assert not summarize([{**row, "time_control": malformed} for row in rows])[
                    "positive"
                ]
            assert not summarize([*rows, {**rows[0], "choice": "alternative_capture"}])["positive"]
            assert not summarize([{**row, "date": rows[0]["date"]} for row in rows])["positive"]

            from chess_coach.opening_fit_rank import rank

            candidates = [
                {"uci": move, "profile": {"center": {"valid": 10}}} for move in ("low", "high")
            ]
            counts = {
                "low": {"sampled": 5, "valid": 5, "available": 2},
                "high": {"sampled": 10, "valid": 10, "available": 10},
            }
            assert rank(candidates, counts, summarize(rows)) == "high"
            assert rank(candidates, counts, summarize(rows[:2])) is None
            assert (
                rank(candidates, {**counts, "low": {**counts["low"], "valid": 4}}, summarize(rows))
                is None
            )
            overlap = {**counts, "low": {"sampled": 10, "valid": 5, "available": 2}}
            assert rank(candidates, overlap, summarize(rows)) is None
            tied = {**counts, "low": {"sampled": 10, "valid": 10, "available": 10}}
            assert rank(candidates, tied, summarize(rows)) is None

            # Later-branch fit uses real imported PGNs and current owned choice reports.
            import hashlib

            import chess_coach.opening_reference_source as reference_source
            import chess_coach.web_opening_later as later_web
            import chess_coach.web_repertoire as repertoire_web
            from chess_coach.opening_fit_context_index import build as build_context
            from chess_coach.opening_fit_later import assess as later_assess
            from chess_coach.opening_profile_index import build as build_previous
            from chess_coach.opening_reference_source import SOURCE_NAME

            lines = (
                "e4 e5 Nf3 d5 exd5 Qxd5 Nc3 Qe6+ Be2 Nf6 O-O Bd6 d4 e4 Ne5 O-O Bf4 Nbd7 Nxd7 Bxd7",
                "e4 e5 Bc4 Nc6 Nf3 Nf6 d3 Be7 O-O O-O Re1 d6 c3 a6 Nbd2 b5 Bb3 Be6 Bc2 d5",
            )

            def make_public(unknown):
                values = []
                for branch, text in enumerate(lines):
                    for index in range(5):
                        game = chess.pgn.Game()
                        game.headers.update(
                            White=f"Public {branch}-{index}",
                            Black=f"Other {branch}-{index}",
                            Result="1-0",
                            Date="2026.09.01",
                        )
                        if not (unknown and branch == 1 and index == 0):
                            game.headers["TimeControl"] = "600+0"
                        board, node = game.board(), game
                        for san in text.split():
                            move = board.parse_san(san)
                            node = node.add_variation(move)
                            board.push(move)
                        values.append(str(game))
                return "\n\n".join(values)

            for name, unknown in (("known", False), ("unknown", True), ("legacy", False)):
                root_path = tmp_path / name
                directory = root_path / ".runtime" / "planning"
                directory.mkdir(parents=True, mode=0o700)
                archive = directory / SOURCE_NAME
                archive.write_bytes(b"synthetic bounded archive")
                sample_pgn = make_public(unknown)
                with patch.context() as source_patch:
                    source_patch.setattr(reference_source, "SOURCE_BYTES", archive.stat().st_size)
                    source_patch.setattr(
                        reference_source,
                        "SOURCE_SHA256",
                        hashlib.sha256(archive.read_bytes()).hexdigest(),
                    )
                    source_patch.setattr(
                        reference_source,
                        "_decode",
                        lambda _file, value=sample_pgn: (value.encode(), False),
                    )
                    build = build_previous if name == "legacy" else build_context
                    assert build(root_path, "learner")["accepted"] == 10

            def later_execute(_db, snapshot, _config, _deadline):
                board, position = snapshot["board"], snapshot["position"]
                pvs = ("e4d5 d8d5 b1c3 d5d6", "b1c3 d5e4 c3e4 f8b4")
                raw = [
                    {
                        "pv": [chess.Move.from_uci(move) for move in line.split()],
                        "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                        "nodes": 500,
                        "depth": 5,
                        "time": 0.05,
                    }
                    for line in pvs
                ]
                lines, invalid = native(position, board, raw)
                assert not invalid
                return (
                    "complete",
                    "comparable",
                    {
                        "scout": {"lines": lines},
                        "final": {"lines": lines, "roots": ["e4d5", "b1c3"]},
                        "engine": {},
                        "runtime_engine": {},
                    },
                )

            later_games = []
            patch.setattr(purpose_worker, "execute", later_execute)
            for index in range(3):
                own_pgn = (
                    f'[Event "Later fixture"]\n[White "learner"]\n[Black "later-{index}"]\n'
                    f'[UTCDate "2026.01.02"]\n[UTCTime "12:00:0{index}"]\n'
                    '[TimeControl "600+0"]\n[Result "*"]\n\n'
                    "1. e4 e5 2. Nf3 d5 3. exd5 Qxd5 4. Nc3 Qe6+ *\n"
                )
                ingest_pgn(owned, own_pgn)
                game_id = owned.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
                decision_id = owned.connection.execute(
                    "SELECT id FROM positions WHERE game_id=? AND ply=3", (game_id,)
                ).fetchone()[0]
                capture_id = owned.connection.execute(
                    "SELECT id FROM positions WHERE game_id=? AND ply=5", (game_id,)
                ).fetchone()[0]
                request_id = create(owned, capture_id, "learner", engine_path=sys.executable)[
                    "request_id"
                ]
                assert purpose_worker.run(owned, request_id, "learner")["status"] == "complete"
                cycle = owned.connection.execute(
                    "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
                    (
                        learner_key("learner"),
                        101 + 4 * index,
                        json.dumps(
                            {
                                "early_center_policy": "early-center-v1",
                                "early_center_targeted": True,
                            }
                        ),
                    ),
                ).lastrowid
                owned.connection.execute(
                    "INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id) VALUES(?,'control',?,?,'complete','fixture',?)",
                    (cycle, game_id, capture_id, request_id),
                )
                owned.connection.commit()
                later_games.append((game_id, decision_id))
            board = chess.Board()
            board.push_san("e4")
            board.push_san("e5")
            choice = {"uci": "f1c4", "san": "Bc4", "child": "synthetic"}
            decision = {
                "game_id": later_games[0][0],
                "position_id": later_games[0][1],
                "ply": 3,
                "color": "white",
                "fen": board.fen(),
                "played": "Nf3",
                "played_uci": "g1f3",
                "opening": {
                    "source_url": "https://example.invalid",
                    "version": "fixture",
                    "content_revision": 1,
                },
                "analysis": {"status": "unavailable"},
                "catalog": {"parent": position_key(board), "items": [choice], "truncated": False},
            }
            outcome = later_assess(owned, tmp_path / "known", "learner", decision, choice)
            assert outcome["status"] == "checked"
            assert outcome["owned"]["branches"]["g1f3"]["games"] == 3
            assert outcome["owned"]["branches"]["g1f3"]["played_capture"] == 3
            assert outcome["public"]["g1f3"]["available"] == 5
            assert outcome["public"]["f1c4"]["available"] == 0
            assert outcome["recommended"] == "g1f3"
            uncertain = later_assess(owned, tmp_path / "unknown", "learner", decision, choice)
            assert uncertain["public"]["f1c4"]["unknown_control"] == 1
            assert uncertain["recommended"] is None
            with patch.context() as legacy_source:
                legacy_source.setattr(sqlite3, "connect", real_connect)
                legacy = later_assess(owned, tmp_path / "legacy", "learner", decision, choice)
            assert legacy["public"]["g1f3"]["unknown_control"] == 5
            assert legacy["recommended"] is None

            # A qualifying choice before a later decision is not attributed to that branch.
            later_board = chess.Board()
            for san in lines[0].split()[:6]:
                later_board.push_san(san)
            later_decision = {
                **decision,
                "ply": 7,
                "fen": later_board.fen(),
                "played_uci": "b1c3",
                "catalog": {**decision["catalog"], "parent": position_key(later_board)},
            }
            later_outcome = later_assess(
                owned, tmp_path / "known", "learner", later_decision, choice
            )
            assert later_outcome["public"]["b1c3"]["valid"] == 5
            assert later_outcome["public"]["b1c3"]["available"] == 0
            assert later_outcome["owned"]["excluded"]["before_decision"] >= 3
            assert later_outcome["recommended"] is None

            # Existing browser gating accepts the qualified legal same-search rehearsal.
            comparison = {
                "status": "complete",
                "work": {"nodes": 100},
                "lines": [
                    {"root_move": "g1f3", "pv": "g1f3 d7d5 e4d5", "score_value": 0, "depth": 5},
                    {"root_move": "f1c4", "pv": "f1c4 b8c6 g1f3", "score_value": 0, "depth": 5},
                ],
            }
            with patch.context() as browser:
                browser.setattr(repertoire_web, "database", lambda: owned)
                browser.setattr(later_web, "database", lambda: owned)
                browser.setattr(repertoire_web, "inspect", lambda *_args, **_kwargs: decision)
                browser.setattr(
                    repertoire_web, "statuses", lambda *_args, **_kwargs: {"f1c4": comparison}
                )
                browser.setitem(app.config, "PROJECT_ROOT", str(tmp_path / "known"))
                browser_url = f"/repertoire/games/{later_games[0][0]}/openings/{later_games[0][1]}?opportunities=f1c4"
                before_read = (owned.connection.total_changes, public.total_changes)
                page = client.get(browser_url, base_url="https://coach.invalid", headers=headers)
                assert (
                    page.status_code == 200 and b"Later center-learning opportunities" in page.data
                )
                assert b"5 of 5 valid public examples" in page.data
                assert b"bounded examples support more later opportunities for Nf3" in page.data
                assert (owned.connection.total_changes, public.total_changes) == before_read
                comparison["lines"][1]["score_value"] = -51
                rejected = client.get(
                    browser_url, base_url="https://coach.invalid", headers=headers
                )
                assert b"lacks a current qualified same-search rehearsal" in rejected.data

            # Acquire, decode and index a recent CC0 prefix using a synthetic HTTP provider.
            import base64
            import random
            import subprocess

            import httpx

            from chess_coach.opening_recent_acquire import acquire
            from chess_coach.opening_recent_index import build as build_recent
            from chess_coach.opening_recent_source import PREFIX_BYTES, PREFIX_NAME, URL

            def rated_game(
                branch, number, control, *, missing_rating=False, berserk=False, moves=None
            ):
                game = chess.pgn.Game()
                game.headers.update(
                    Event="Rated Blitz game",
                    White=f"Reference {branch}-{number}",
                    Black=f"Peer {branch}-{number}",
                    Result="1-0",
                    Date="2026.10.01",
                    TimeControl=control,
                    WhiteElo="1700",
                    BlackElo="1650",
                )
                if missing_rating:
                    del game.headers["WhiteElo"]
                if berserk:
                    game.headers["WhiteBerserk"] = "true"
                board, node = game.board(), game
                for san in (moves or lines[branch]).split():
                    move = board.parse_san(san)
                    node = node.add_variation(move)
                    board.push(move)
                return str(game)

            def long_line(start, *, repeated=False):
                board, moves = chess.Board(), []
                for san in start.split():
                    move = board.parse_san(san)
                    moves.append(board.san(move))
                    board.push(move)
                while len(moves) < (100 if repeated else 130):
                    if repeated and len(moves) == 60:
                        for uci in ("f3g5", "g8h8", "g5f3", "h8g8"):
                            move = board.parse_uci(uci)
                            moves.append(board.san(move))
                            board.push(move)
                        continue
                    for move in sorted(board.legal_moves, key=lambda value: value.uci()):
                        if move.promotion:
                            continue
                        following = board.copy()
                        following.push(move)
                        if not following.is_repetition(2) and not following.is_game_over(
                            claim_draw=True
                        ):
                            moves.append(board.san(move))
                            board.push(move)
                            break
                    else:
                        pytest.fail("synthetic legal continuation unavailable")
                return moves

            long_moves = long_line(lines[0])
            alternative_long_moves = long_line(lines[1], repeated=True)
            rated_games = [rated_game(0, i, "300+0") for i in range(12)]
            rated_games += [rated_game(0, 100, "600+0", berserk=True)]
            rated_games += [rated_game(0, 101, "600+0", missing_rating=True)]
            supported_capture = (
                "e4 e5 Bc4 Nc6 Nf3 a6 Nc3 Na5 Nxe5 Nxc4 Nxc4 d5 exd5 Qxd5 Ne3 Qd8 O-O Nf6 Re1 Be7"
            )
            supported_fork = (
                "e4 e5 Nf3 g5 Nxe5 d5 Bb5+ Qd7 exd5 Qxb5 Nxf7 Kxf7 h3 Qxd5 b3 Qxb3 axb3 Bxh3 d3 Nc6"
            )
            nomination_fork = (
                "e4 Nc6 Nf3 e5 Bc4 Nb8 Bf1 g5 Nxe5 d5 Bb5+ Qd7 exd5 Qxb5 "
                "Nxf7 Kxf7 h3 Qxd5 b3 Qxb3 axb3 Bxh3 Qg4 Ne7"
            )
            rated_games.append(rated_game(0, 299, "1800+0", moves=nomination_fork))
            rated_games.append(
                rated_game(0, 300, "1800+0", moves=" ".join(long_line(nomination_fork)))
            )
            # Same decision, independent synthetic public games: bounded style
            # contrast and a separate candidate-branch material fork witness.
            fit_low = "e4 Nc6 Nf3 e5 Nxe5 Nxe5 a3 a5 Ra2 a4 Ra1 Ra5 Ra2 Ra6 Ra1 Ra7 Ra2 Ra5 Ra1 Ra6"
            fit_quiet = (
                "e4 Nc6 Nf3 e5 Bc4 Nb8 Nc3 Nf6 d3 Be7 O-O O-O Re1 d6 Be3 c6 Qd2 Nbd7 Rad1 Re8"
            )
            fork_alternative = (
                "e4 Nc6 Nf3 e5 Nc3 a6 Bc4 Nb8 Bf1 g5 Nxe5 d5 Bb5+ Qd7 exd5 Qxb5 "
                "Nxf7 Kxf7 h3 Qxd5 b3 Qxb3 axb3 Bxh3 Qg4 Ne7"
            )
            rated_games += [
                rated_game(0, 310, "1800+0", moves=" ".join(nomination_fork.split()[:20]))
            ]
            rated_games += [rated_game(0, 311 + i, "1800+0", moves=fit_quiet) for i in range(2)]
            rated_games += [rated_game(0, 320 + i, "1800+0", moves=fit_low) for i in range(5)]
            rated_games.append(rated_game(0, 330, "1800+0", moves=fork_alternative))
            continuation_fork = (
                "e4 e5 Nf3 g5 Nxe5 d5 Bb5+ Qd7 exd5 Qxb5 Nxf7 Kxf7 h3 Qxd5 b3 Qxb3 "
                "axb3 Bxh3 Rg1 h6 Rf1 c6 c3 Ne7 Rg1 c5 Ra2 Rh7 Rb2 b6 Rc2 Rh8 "
                "Rf1 Nf5 Rh1 Nd6 Na3 Ne8 d3 Nc6"
            )
            # Synthetic legal histories, with recorded action at the witnessed decision.
            pre_history_text = (
                "e2e4 e7e5 g1f3 f8e7 f3e5 e7a3 b1a3 f7f6 e5d7 g8e7 d7f6 g7f6 d2d3 "
                "d8d3 d1d3 c8h3 g2h3 c7c5 d3d2 e8f8 d2g5 f6g5 c1g5 f8f7 f2f4 e7c6 "
                "g5d8 h8d8 a3c4 a7a6 e1e2 c6e5 a1c1 d8g8 c4e3 b7b5 e3d1 c5c4 c1b1 "
                "e5g6 h3h4 g6f4 e2f3 f7f6 f1c4 b5c4 h2h3 f4h3 a2a4 g8d8 f3g4 f6e6 "
                "d1e3 d8c8"
            )
            pre_history = pre_history_text.split()
            created_history_text = (
                "e2e4 e7e5 f1c4 b7b6 c4f7 e8f7 g1h3 g8h6 h1g1 f7e8 g1f1 d8g5 h3g5 "
                "f8b4 g5h7 c8a6 f1h1 b4d2 c1d2 h6g8 d2e3 h8h7 e3b6 c7b6 d1d7 e8d7 "
                "a2a3 h7h2 h1h2 d7d6 a1a2 a6e2 e1e2 d6c5 f2f4 e5f4 h2h1 c5c4 b2b4 "
                "g7g6 h1e1 g8e7 a3a4 c4b4 e2f1 b6b5 a4b5 b4b5 a2a7 a8a7 f1g1 f4f3 "
                "g2f3 a7a6 e4e5 a6a8 b1d2 e7d5 d2b1 d5c3 e1e3 c3b1 f3f4 a8a7 e3e2 "
                "a7c7 e2g2 c7c2 g2c2 b1c3"
            )
            created_history = created_history_text.split()
            prevention_fixtures = {
                "pre_existing": {"history": pre_history, "recorded": "e3f1"},
                "created": {"history": created_history, "recorded": "c2c1"},
                "pre_existing_good": {"history": pre_history, "recorded": "g4h5"},
            }

            checked_lines = (
                lines[0] + " Bh6 Bxh2+ Kxh2 Qe5+ Kg1 Qb5 Qc1 g5 Nd1 Nd5 b3 Qb6 Qf4 a6",
                lines[1] + " h4 g6 Nd4 Nxd4 b3 Nf3+ Qxf3 Kh8 Bb2 Qb8 Rab1 Bc5 Rec1 Kg8",
            )
            rated_games += [
                rated_game(
                    branch,
                    200 + i,
                    "600+0",
                    moves=(
                        supported_capture
                        if branch == 1 and i == 0
                        else supported_fork
                        if branch == 0 and i == 0
                        else continuation_fork
                        if branch == 0 and i == 1
                        else " ".join(alternative_long_moves)
                        if branch == 1 and i == 2
                        else checked_lines[branch]
                        if (branch == 0 and i == 4) or (branch == 1 and i == 3)
                        else lines[1]
                        + " Nd4 exd4 Nf1 Bf5 h3 Bd6 Nd2 Bh2+ Kxh2 Qd6+ f4 Rfb8 Rh1 Re8"
                        if branch == 1 and i == 4
                        else None
                    ),
                )
                for branch in (0, 1)
                for i in range(5)
            ]
            queenless = "e4 e5 Nf3 Nc6 Bb5 a6 Bxc6 dxc6 Nxe5 Qd4 Nf3 Qxe4+ Qe2 Qxe2+ Kxe2 Kd7"
            promotion = "e4 e5 Nf3 h5 a4 h4 a5 h3 a6 hxg2 axb7 gxh1=Q bxa8=Q"
            rated_games += [
                rated_game(0, 300, "600+0", moves=queenless),
                rated_game(0, 301, "600+0", moves=promotion),
                rated_game(0, 302, "600+0", moves=" ".join(long_moves)),
            ]
            noise = base64.b64encode(random.Random(743).randbytes(1_400_000)).decode()
            synthetic = ("\n\n".join(rated_games) + "\n\n{" + noise).encode()
            compressed = subprocess.run(
                ["/usr/bin/zstd", "-q", "-c"], input=synthetic, stdout=subprocess.PIPE, check=True
            ).stdout
            assert len(compressed) > PREFIX_BYTES
            prefix = compressed[:PREFIX_BYTES]
            recent_root = tmp_path / "recent"
            recent_planning = recent_root / ".runtime" / "planning"
            recent_planning.mkdir(parents=True, mode=0o700)
            requests = []

            def respond(request):
                requests.append(request)
                assert str(request.url) == URL
                assert request.headers["range"] == f"bytes=0-{PREFIX_BYTES - 1}"
                assert "authorization" not in request.headers and "cookie" not in request.headers
                return httpx.Response(
                    206,
                    headers={
                        "Content-Range": f"bytes 0-{PREFIX_BYTES - 1}/{PREFIX_BYTES * 2}",
                        "Content-Length": str(PREFIX_BYTES),
                        "ETag": '"synthetic"',
                    },
                    content=prefix,
                    request=request,
                )

            invalid_root = tmp_path / "invalid-response"
            (invalid_root / ".runtime" / "planning").mkdir(parents=True, mode=0o700)
            with (
                httpx.Client(
                    transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, content=b"not a range", request=request)
                    )
                ) as fake,
                pytest.raises(ValueError, match="requested range"),
            ):
                acquire(invalid_root, "learner", client=fake)
            assert not (invalid_root / ".runtime" / "planning" / PREFIX_NAME).exists()
            retry_root = tmp_path / "retry-response"
            (retry_root / ".runtime" / "planning").mkdir(parents=True, mode=0o700)
            with httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        429, headers={"Retry-After": "120"}, request=request
                    )
                )
            ) as fake:
                with pytest.raises(ValueError, match="retry delay"):
                    acquire(retry_root, "learner", client=fake)
                with pytest.raises(ValueError, match="remains active"):
                    acquire(retry_root, "learner", client=fake)
            with httpx.Client(transport=httpx.MockTransport(respond)) as fake:
                receipt = acquire(recent_root, "learner", client=fake)
                with pytest.raises(ValueError, match="already exists"):
                    acquire(recent_root, "learner", client=fake)
            assert len(requests) == 1 and not receipt["whole_archive_checksum_verified"]
            assert (recent_planning / PREFIX_NAME).stat().st_size == PREFIX_BYTES
            coverage = build_recent(recent_root, "learner")
            assert coverage["accepted"] == 38 and coverage["truncated"]
            from chess_coach.opening_profile_source import profile as recent_before_history

            unavailable = recent_before_history(
                owned, recent_root, "learner", decision, "g1f3", "recent", time.monotonic() + 30
            )
            assert unavailable["later_history"]["status"] == "unavailable"
            from chess_coach.opening_recent_source import INDEX_NAME as OLD_INDEX

            old_index = recent_planning / OLD_INDEX
            old_index_hash = hashlib.sha256(old_index.read_bytes()).hexdigest()
            import chess_coach.ops_opening_recent_import as recent_cli

            with patch.context() as history_cli:
                history_cli.setenv("CHESS_SUBJECT", "learner")
                history_cli.setattr(
                    sys,
                    "argv",
                    ["opening-recent", "build-full-history", "--project-root", str(recent_root)],
                )
                recent_cli.main()
            assert hashlib.sha256(old_index.read_bytes()).hexdigest() == old_index_hash
            from chess_coach.opening_full_history_build import INDEX_NAME as FULL_INDEX

            full_index = recent_planning / FULL_INDEX
            assert full_index.stat().st_mode & 0o777 == 0o400
            assert full_index.stat().st_size <= 20_000_000

            # Over-limit records are excluded before claiming legal validation.
            from chess_coach.opening_full_history_parse import parser as full_parser
            from chess_coach.opening_full_history_store import MAX_BYTES, configure
            from chess_coach.opening_full_history_summary import summarize as full_summary

            excessive = chess.pgn.Game()
            node = excessive
            for ply in range(513):
                node = node.add_variation(chess.Move.from_uci("g1f3" if ply % 2 == 0 else "g8f6"))
            rejected = [0]
            assert full_parser(lambda: None, rejected)(excessive, "", 1) is None
            assert rejected == [1]
            import io

            from chess_coach.opening_reference_visitor import read_game as read_timed_game

            visits = [0]

            def expire_mid_game():
                visits[0] += 1
                if visits[0] == 5:
                    raise TimeoutError("synthetic deadline")

            with pytest.raises(TimeoutError):
                read_timed_game(io.StringIO("1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 1-0"), expire_mid_game)
            from chess_coach.public_training_pgn_lex import valid_movetext

            visits[0] = 0
            with pytest.raises(TimeoutError):
                valid_movetext("1. e4 e5 2. Nf3 Nc6 1-0", check=expire_mid_game)
            limited = real_connect(":memory:")
            configure(limited, time.monotonic() + 30)
            page_size = limited.execute("PRAGMA page_size").fetchone()[0]
            max_pages = limited.execute("PRAGMA max_page_count").fetchone()[0]
            assert page_size * max_pages <= MAX_BYTES
            limited.execute("INSERT INTO histories VALUES(?,?,?)", (1, "0" * 64, "[]"))
            unavailable_history = full_summary(
                limited, [(1, 2, "{}")], decision, "g1f3", time.monotonic() + 30
            )
            assert unavailable_history["unsupported"] == 1
            interrupted_history = full_summary(
                limited, [(1, 2, "{}")], decision, "g1f3", time.monotonic() - 1
            )
            assert interrupted_history["incomplete"] == 1 and interrupted_history["interrupted"]
            limited.close()
            import tempfile

            from chess_coach.opening_reference_decode import decode

            with tempfile.TemporaryFile(dir=recent_planning) as broken:
                broken.write(b"invalid compressed data")
                broken.seek(0)
                with pytest.raises(ValueError, match="could not be decoded"):
                    decode(broken, allow_partial=True)
            recent = later_assess(owned, recent_root, "learner", decision, choice, source="recent")
            assert recent["status"] == "checked"
            assert recent["public"]["g1f3"]["excluded_context"] == 13
            assert recent["public"]["g1f3"]["unknown_context"] == 1
            assert recent["public"]["g1f3"]["matched_candidates"] == 8
            assert recent["public"]["g1f3"]["available"] == 6
            assert recent["recommended"] == "g1f3"
            from chess_coach.opening_profile_source import profile as matched_profile

            profile = matched_profile(
                owned, recent_root, "learner", decision, "g1f3", "recent", time.monotonic() + 30
            )
            assert profile["decision_ply"] == 3 and profile["control"] == "600+0"
            assert (
                profile["matched_candidates"],
                profile["excluded_context"],
                profile["unknown_context"],
            ) == (8, 13, 1)
            assert profile["games"] == 8 and profile["source_metadata"]["source_month"] == "2026-10"
            assert all(not item["site"] for item in profile["examples"])
            assert profile["queens"]["one_each"] == 8
            assert profile["queens"]["queenless_observed"] == 1
            assert profile["queens"]["one_or_imbalanced"] == 3
            late = profile["later_history"]
            assert late["status"] == "complete" and late["matched_candidates"] == 8
            assert late["example"]["example"]["ply"] > 88
            assert late["example"]["example"]["window_start"] == late["example"]["total_plies"] - 35
            assert late["example"]["example"]["window_end"] == late["example"]["total_plies"]
            assert late["censored"] >= 1 and late["ended_before_later"] >= 1
            assert late["example"]["record_ended"] and not late["example"]["board_terminal"]
            assert late["coverage"]["over_512_unvalidated"] == 0
            assert late["policy"]["tail_positions"] == 36
            assert late["policy"]["maximum_game_plies"] == 512
            assert profile["check_responses"]["played_king"] >= 1
            assert profile["check_responses"]["example"]["played"]["kind"] == "king"
            assert profile["check_responses"]["unsupported"] >= 1
            assert len(profile["index_sha256"]) == 64
            assert profile["queens"]["unsupported"] == 1
            assert profile["queens"]["ended"] == 5 and profile["queens"]["cutoff"] == 2
            from chess_coach.opening_profile_recent import profile as recent_profile

            qboard = chess.Board()
            for san in queenless.split()[:14]:
                qboard.push_san(san)
            qdecision = {"ply": 15, "catalog": {"parent": position_key(qboard)}}
            on_capture = recent_profile(
                recent_root, "learner", qdecision, "e1e2", "600+0", time.monotonic() + 30
            )
            assert on_capture["games"] == 1
            assert on_capture["queens"]["start_imbalanced"] == 1
            assert on_capture["queens"]["queenless_observed"] == 1
            qboard.push_san("Kxe2")
            qdecision = {"ply": 16, "catalog": {"parent": position_key(qboard)}}
            already = recent_profile(
                recent_root, "learner", qdecision, "e8d7", "600+0", time.monotonic() + 30
            )
            assert already["queens"]["preexisting_queenless"] == 1
            assert already["queens"]["queenless_observed"] == 0
            frontier_board = chess.Board()
            for san in long_moves[:19]:
                frontier_board.push_san(san)
            frontier_move = frontier_board.parse_san(long_moves[19]).uci()
            frontier = recent_profile(
                recent_root,
                "learner",
                {"ply": 20, "catalog": {"parent": position_key(frontier_board)}},
                frontier_move,
                "600+0",
                time.monotonic() + 30,
            )
            assert frontier["queens"]["frontier"] == 1
            assert frontier["check_responses"]["frontier"] == 1

            # Checkmate is terminal; a checked final position without a reply is unknown.
            from chess_coach.opening_check_response_replay import replay as check_replay

            memory = real_connect(":memory:")
            memory.execute(
                "CREATE TABLE moves(game_id INTEGER, ply INTEGER, parent TEXT, uci TEXT, san TEXT)"
            )
            one_reply = "b3 g5 a3 Bg7 d3 Bxa1 Kd2 Be5 h3 Nf6 Ke1 Nc6 f4 d5 Bb2 gxf4 Nd2 Ng8 Nc4 e6 Nd2 Qh4+ g3"
            for game_no, text in enumerate(
                ("f3 e5 g4 Qh4#", "e4 e5 Bc4 Be7 d4 Bb4+", one_reply), 1
            ):
                board = chess.Board()
                for ply, san in enumerate(text.split(), 1):
                    move = board.parse_san(san)
                    memory.execute(
                        "INSERT INTO moves VALUES(?,?,?,?,?)",
                        (game_no, ply, position_key(board), move.uci(), board.san(move)),
                    )
                    board.push(move)
            initial = {"ply": 1, "catalog": {"parent": position_key(chess.Board())}}
            mate = check_replay(memory, 1, 4, initial, "f2f3", time.monotonic() + 30)
            assert mate["status"] == "ended" and mate["events"][0]["checkmate"]
            assert mate["events"][0]["legal_responses"] == 0
            pending = check_replay(memory, 2, 6, initial, "e2e4", time.monotonic() + 30)
            assert pending["status"] == "ended" and pending["unanswered"]
            assert not pending["events"]
            forced = check_replay(memory, 3, 23, initial, "b2b3", time.monotonic() + 30)
            assert any(item["legal_responses"] == 1 for item in forced["events"])
            from chess_coach.opening_check_response_summary import summarize as check_summary

            interrupted = check_summary(
                memory, [(2, 6, "{}")], initial, "e2e4", "600+0", time.monotonic() - 1
            )
            assert interrupted["interrupted"] and interrupted["preparation_incomplete"] == 1
            memory.close()
            owned.connection.execute("BEGIN")
            owned.connection.execute(
                "UPDATE games SET time_control=NULL WHERE id=?", (decision["game_id"],)
            )
            unknown_control = matched_profile(
                owned,
                recent_root,
                "learner",
                decision,
                "g1f3",
                "recent",
                time.monotonic() + 30,
            )
            assert unknown_control["control"] == "unknown" and unknown_control["games"] == 0
            assert unknown_control["check_responses"]["status"] == "unavailable"
            assert unknown_control["unknown_context"] >= 8
            owned.connection.rollback()
            import chess_coach.opening_profile_recent as recent_reader

            locate = recent_reader.locate
            calls = []

            def changed_source(*args):
                current = locate(*args)
                calls.append(current)
                return current if len(calls) == 1 else (current[0], ("changed",), *current[2:])

            with patch.context() as changed:
                changed.setattr(recent_reader, "locate", changed_source)
                assert (
                    matched_profile(
                        owned,
                        recent_root,
                        "learner",
                        decision,
                        "g1f3",
                        "recent",
                        time.monotonic() + 30,
                    )
                    is None
                )
            missing = matched_profile(
                owned,
                tmp_path / "not-present",
                "learner",
                decision,
                "g1f3",
                "recent",
                time.monotonic() + 30,
            )
            assert missing is None
            exact_later = matched_profile(
                owned,
                recent_root,
                "learner",
                later_decision,
                "b1c3",
                "recent",
                time.monotonic() + 30,
            )
            assert exact_later["decision_ply"] == 7 and exact_later["games"] == 4
            wrong_ply = matched_profile(
                owned,
                recent_root,
                "learner",
                {**later_decision, "ply": 9},
                "b1c3",
                "recent",
                time.monotonic() + 30,
            )
            assert wrong_ply["games"] == 0
            comparison["lines"][1]["score_value"] = 0
            with patch.context() as browser:
                browser.setattr(repertoire_web, "database", lambda: owned)
                browser.setattr(later_web, "database", lambda: owned)
                browser.setattr(repertoire_web, "inspect", lambda *_args, **_kwargs: decision)
                browser.setattr(
                    repertoire_web, "statuses", lambda *_args, **_kwargs: {"f1c4": comparison}
                )
                browser.setitem(app.config, "PROJECT_ROOT", str(recent_root))
                import chess_coach.web_opening_profile as profile_web

                browser.setattr(profile_web, "database", lambda: owned)
                browser.setattr(profile_web, "inspect", lambda *_args, **_kwargs: decision)
                import chess_coach.opening_explore_comparison as profile_comparison

                browser.setattr(
                    profile_comparison,
                    "statuses",
                    lambda *_args, **_kwargs: {"f1c4": comparison},
                )
                page = client.get(
                    browser_url + "&reference=recent",
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert page.status_code == 200 and b"Recent CC0 standard-rated source" in page.data
                assert b"whole archive checksum was not verified" in page.data
                assert b"13 excluded and 1 with missing context" in page.data
                assert b"Recorded source ratings range from 1650 to 1700" in page.data
                assert (
                    b"nominal time control does not establish actual thinking time"
                    in page.data.lower()
                )
                match = re.search(
                    r'<a href="([^"]+)">Source and branch examples</a>', page.get_data(as_text=True)
                )
                assert match and "reference=recent" in html.unescape(match.group(1))
                profile_page = client.get(
                    html.unescape(match.group(1)), base_url="https://coach.invalid", headers=headers
                )
                assert profile_page.status_code == 200
                assert b"Recent rated sample for the exact move at ply 3" in profile_page.data
                assert b"Individual game links were not retained" in profile_page.data
                assert b"Observed queenless positions" in profile_page.data
                assert b"Observed check responses" in profile_page.data
                assert b"Later recorded positions" in profile_page.data
                assert b"Public archive example" in profile_page.data
                assert b"Public archive example" in profile_page.data
                assert b"do not establish accuracy" in profile_page.data
                assert b"A later queenless position was observed in 1 games" in profile_page.data
                assert b"Rehearse the checked lines" in profile_page.data
                comparison["lines"][1]["score_value"] = -51
                blocked = client.get(
                    html.unescape(match.group(1)), base_url="https://coach.invalid", headers=headers
                )
                assert b"Rehearse the checked lines" not in blocked.data
                comparison["lines"][1]["score_value"] = 0

            # The standalone command reopens a project-contained copy read-only and
            # derives the decision from the actual classified owned game.
            from chess_coach.opening_classification import classify_game
            from chess_coach.opening_profile_cli_report import report as cli_profile
            from chess_coach.opening_snapshot import SOURCE, VERSION

            classify_game(owned, later_games[0][0], version=VERSION, source_url=SOURCE)

            # A long legal owned game must fit each source verification independently.
            long_game = chess.pgn.Game()
            long_game.headers.update(
                White="learner",
                Black="long fixture",
                Result="*",
                TimeControl="600+0",
                UTCDate="2026.01.02",
                UTCTime="12:01:00",
            )
            board, node = long_game.board(), long_game
            for san in lines[0].split():
                move = board.parse_san(san)
                node = node.add_variation(move)
                board.push(move)
            rng = random.Random(0)
            while len(board.move_stack) < 300:
                moves = list(board.legal_moves)
                rng.shuffle(moves)
                moves.sort(
                    key=lambda move: (
                        board.is_capture(move),
                        (board.piece_type_at(move.from_square) == chess.PAWN)
                        if board.halfmove_clock < 115
                        else (board.piece_type_at(move.from_square) != chess.PAWN),
                    )
                )
                for move in moves:
                    if move.promotion:
                        continue
                    following = board.copy()
                    following.push(move)
                    if not following.is_game_over(claim_draw=False):
                        node = node.add_variation(move)
                        board.push(move)
                        break
                else:
                    pytest.fail("long legal continuation unavailable")
            ingest_pgn(owned, str(long_game))
            long_id = owned.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
            long_position = owned.connection.execute(
                "SELECT id FROM positions WHERE game_id=? AND ply=3", (long_id,)
            ).fetchone()[0]
            classify_game(owned, long_id, version=VERSION, source_url=SOURCE)
            data = recent_root / ".runtime" / "data"
            data.mkdir()
            db_path = data / "synthetic.sqlite"
            copied = real_connect(db_path)
            owned.connection.backup(copied)
            copied.close()
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            with patch.context() as cli:
                cli.setenv("CHESS_DB", str(db_path))
                cli.delenv("CHESS_SCHEMA_COMPAT", raising=False)
                report = cli_profile(recent_root, "learner", *later_games[0], "f1c4", "recent")
                assert report["decision_ply"] == 3 and report["played"]["games"] == 8
                assert report["played"]["queens"]["queenless_observed"] == 1
                assert report["public_preparation"] is None
                # Rechecking queue and proof bindings gives each the existing
                # bounded history scope while retaining one shared deadline.
                import chess_coach.opening_queue_binding as long_binding
                from chess_coach.opening_decision import inspect as long_inspect
                from chess_coach.opening_profile_cli_db import private_database
                from chess_coach.opening_queue_budget import BrowserBudget
                from chess_coach.opening_recommendation_paths import inputs as recommendation_inputs

                with cli.context() as long_config:
                    long_config.setattr(long_binding, "ENGINE", sys.executable)
                    with private_database(recent_root, "learner") as long_db:
                        long_decision = long_inspect(long_db, long_id, long_position, "learner")
                        long_budget = BrowserBudget(long_db)
                        long_budget.expires = min(long_budget.expires, time.monotonic() + 25)
                        watched = recommendation_inputs(
                            long_db, recent_root, "learner", long_decision, long_budget
                        )
                        assert watched and len(watched) <= 200
                for branch in ("played", "alternative"):
                    tail = report[branch]["later_history"]
                    assert tail["example"]["example"]["ply"] > 52
                    assert (
                        tail["example"]["example"]["window_end"] == tail["example"]["total_plies"]
                    )
                assert report["played"]["later_history"]["example"]["example"]["ply"] > 88
                assert report["alternative"]["later_history"]["example"]["example"][
                    "repetition_observed"
                ]
                assert report["played"]["check_responses"]["played_king"] >= 1
                assert report["alternative"]["check_responses"]["played_capture"] >= 1
                assert report["alternative"]["check_responses"]["played_interposition"] >= 1
                assert report["alternative"]["check_responses"]["multiple_responses"] >= 1
                assert (
                    report["alternative"]["check_responses"]["example"]["played"]["kind"]
                    == "capture"
                )
                with pytest.raises(ValueError):
                    cli_profile(recent_root, "other", *later_games[0], "f1c4", "recent")

                # The actual offline CLI prepares both current and candidate branches.
                import contextlib
                import io
                import sys as public_prep_sys

                import chess_coach.opening_public_proof_replay as public_replay
                import chess_coach.ops_opening_profile as profile_cli

                cli.setenv("CHESS_SUBJECT", "learner")
                cli.setattr(
                    public_prep_sys,
                    "argv",
                    [
                        "opening-profile",
                        "--project-root",
                        str(recent_root),
                        "--game-id",
                        str(later_games[0][0]),
                        "--position-id",
                        str(later_games[0][1]),
                        "--alternative",
                        "f1c4",
                        "--reference",
                        "recent",
                        "--prepare-public",
                    ],
                )
                import types

                import chess_coach.opening_recent_capacity as recent_capacity
                from chess_coach.opening_queue_files import MAX_BYTES as SLOT_MAX_BYTES
                from chess_coach.opening_queue_write import staged

                # A bounded proof fits where the unchanged full-index allowance cannot.
                with cli.context() as scarce:
                    used_kib = (recent_capacity.PROJECT_LIMIT - 96 * 1024 * 1024) // 1024
                    scarce.setattr(
                        recent_capacity,
                        "subprocess",
                        types.SimpleNamespace(
                            run=lambda *_args, **_kwargs: types.SimpleNamespace(
                                stdout=str(used_kib)
                            )
                        ),
                    )
                    with pytest.raises(ValueError, match="project storage reserve"):
                        recent_capacity.check(recent_root, recent_planning)
                    with (
                        pytest.raises(ValueError, match="exceeds limit"),
                        staged(recent_planning / "oversized.json", {"x": "x" * SLOT_MAX_BYTES}),
                    ):
                        pytest.fail("oversized slot was accepted")
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        profile_cli.main()
                prepared = json.loads(output.getvalue())
                assert prepared["branches"]["played"]["selected"] > 0
                assert prepared["branches"]["alternative"]["selected"] > 0
                example = prepared["branches"]["alternative"]["example"]
                assert example["proof"]["status"] == "correct"
                assert example["proof"]["proven_gain_floor"] == 3
                assert prepared["branches"]["played"]["unsupported"] > 0
                artifact_names = set(recent_planning.glob("opening-public-proof-*.json"))
                assert len(artifact_names) == 1

                from chess_coach.opening_profile_cli_report import prepare_public

                long_prepared = prepare_public(
                    recent_root, "learner", long_id, long_position, "f1c4"
                )
                assert long_prepared["branches"]["alternative"]["example"]
                artifact_names = set(recent_planning.glob("opening-public-proof-*.json"))
                assert len(artifact_names) == 2

                # Existing v1 remains readable before and after the combined v2 preparation.
                legacy_hashes = {
                    path: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifact_names
                }
                from chess_coach.opening_public_proof import PUBLICATION_WORKING

                with cli.context() as full_project:
                    used_kib = (
                        recent_capacity.PROJECT_LIMIT
                        - recent_capacity.RESERVE
                        - PUBLICATION_WORKING
                    ) // 1024 + 1
                    full_project.setattr(
                        recent_capacity,
                        "subprocess",
                        types.SimpleNamespace(
                            run=lambda *_args, **_kwargs: types.SimpleNamespace(
                                stdout=str(used_kib)
                            )
                        ),
                    )
                    with pytest.raises(ValueError, match="project storage reserve"):
                        prepare_public(recent_root, "learner", *later_games[0], "f1c4")
                with cli.context() as full_filesystem:
                    full_filesystem.setattr(
                        recent_capacity,
                        "subprocess",
                        types.SimpleNamespace(
                            run=lambda *_args, **_kwargs: types.SimpleNamespace(stdout="0")
                        ),
                    )
                    full_filesystem.setattr(
                        recent_capacity,
                        "shutil",
                        types.SimpleNamespace(
                            disk_usage=lambda *_: types.SimpleNamespace(
                                free=recent_capacity.RESERVE + PUBLICATION_WORKING - 1
                            )
                        ),
                    )
                    with pytest.raises(ValueError, match="filesystem storage reserve"):
                        prepare_public(recent_root, "learner", *later_games[0], "f1c4")
                assert set(recent_planning.glob("opening-public-proof-*.json")) == artifact_names
                assert all(
                    hashlib.sha256(path.read_bytes()).hexdigest() == value
                    for path, value in legacy_hashes.items()
                )
                fallback = cli_profile(recent_root, "learner", *later_games[0], "f1c4", "recent")
                assert (
                    fallback["public_preparation"]["version"]
                    == "public-opening-capture-preparation-v1"
                )
                cli.setattr(
                    public_prep_sys, "argv", [*public_prep_sys.argv[:-1], "--prepare-public-forks"]
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                combined = json.loads(output.getvalue())
                assert combined["version"] == "public-opening-capture-fork-preparation-v2"
                assert combined["fork_policy"]["roots_per_game"] == 64
                assert combined["fork_policy"]["proofs_per_branch"] == 8
                for label in ("played", "alternative"):
                    assert combined["branches"][label]["forks"]["selected"] > 0
                fork = combined["branches"]["played"]["forks"]
                assert fork["material"] >= 1 and not fork["example"]["recorded"]
                assert fork["example"]["recorded_san"] == "d3"
                assert fork["example"]["candidate_san"] == "Qh5+"
                assert fork["example"]["kind"] == "material"
                assert fork["example"]["proof"]["minimum_gain"] == 3
                assert fork["example"]["proof"]["branches"]
                assert fork["incomplete"] and (fork["root_limit"] or fork["proof_limit"])
                assert fork["roots"] <= 64 * fork["selected"] and fork["proofs"] <= 8
                assert combined["branches"]["alternative"]["example"]
                assert all(
                    hashlib.sha256(path.read_bytes()).hexdigest() == value
                    for path, value in legacy_hashes.items()
                )
                artifact_names = set(recent_planning.glob("opening-public-proof-*.json"))
                assert len(artifact_names) == 3

                initial_hashes = {
                    path: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifact_names
                }
                cli.setattr(
                    public_prep_sys,
                    "argv",
                    [*public_prep_sys.argv, "--fork-window", "continuation"],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                later_proof = json.loads(output.getvalue())
                assert later_proof["version"] == "public-opening-capture-fork-continuation-v3"
                assert later_proof["fork_policy"]["offset"] == 36
                later_fork = later_proof["branches"]["played"]["forks"]
                assert later_fork["eligible"] >= later_fork["selected"] > 0
                assert later_fork["ended_before_window"] > 0
                assert later_fork["example"]["kind"] == "material"
                assert later_fork["example"]["ply"] >= later_proof["fork_policy"]["offset"] + 3
                assert later_fork["example"]["candidate_san"] == "Qh5+"
                assert (
                    later_fork["proofs"] <= 8 and later_fork["roots"] <= 64 * later_fork["selected"]
                )
                assert all(
                    hashlib.sha256(path.read_bytes()).hexdigest() == value
                    for path, value in initial_hashes.items()
                )
                artifact_names = set(recent_planning.glob("opening-public-proof-*.json"))
                assert len(artifact_names) == 4

                # A separate bounded source uses the same real catalog pair for both origins.
                prevention_root = tmp_path / "prevention"
                prevention_planning = prevention_root / ".runtime" / "planning"
                prevention_planning.mkdir(parents=True, mode=0o700)
                prevention_data = prevention_root / ".runtime" / "data"
                prevention_data.mkdir(parents=True, mode=0o700)
                prevention_db_path = prevention_data / "synthetic.sqlite"
                source_connection = real_connect(db_path)
                destination_connection = real_connect(prevention_db_path)
                source_connection.backup(destination_connection)
                destination_connection.close()
                source_connection.close()
                prevention_db_hash = hashlib.sha256(prevention_db_path.read_bytes()).hexdigest()
                cli.setenv("CHESS_DB", str(prevention_db_path))
                prevention_games = []
                for label, fixture in prevention_fixtures.items():
                    game = chess.pgn.Game()
                    game.headers.update(
                        Event="Rated Blitz game",
                        White=f"Synthetic {label}",
                        Black=f"Synthetic peer {label}",
                        Result="1-0",
                        Date="2026.10.01",
                        TimeControl="600+0",
                        WhiteElo="1700",
                        BlackElo="1650",
                    )
                    source_board, node = chess.Board(), game
                    history, recorded = fixture["history"], fixture["recorded"]
                    assert isinstance(history, list) and isinstance(recorded, str)
                    for uci in [*history, recorded]:
                        assert isinstance(uci, str)
                        move = source_board.parse_uci(uci)
                        node = node.add_variation(move)
                        source_board.push(move)
                    prevention_games.append(str(game))
                prevention_content = ("\n\n".join(prevention_games) + "\n\n{" + noise).encode()
                prevention_zstd = subprocess.run(
                    ["/usr/bin/zstd", "-q", "-c"],
                    input=prevention_content,
                    stdout=subprocess.PIPE,
                    check=True,
                ).stdout
                assert len(prevention_zstd) > PREFIX_BYTES
                prevention_prefix = prevention_zstd[:PREFIX_BYTES]

                def prevention_response(request):
                    return httpx.Response(
                        206,
                        headers={
                            "Content-Range": f"bytes 0-{PREFIX_BYTES - 1}/{PREFIX_BYTES * 2}",
                            "Content-Length": str(PREFIX_BYTES),
                            "ETag": '"synthetic-prevention"',
                        },
                        content=prevention_prefix,
                        request=request,
                    )

                with httpx.Client(transport=httpx.MockTransport(prevention_response)) as fake:
                    acquire(prevention_root, "learner", client=fake)
                assert build_recent(prevention_root, "learner")["accepted"] == 3
                from chess_coach.opening_full_history_build import build as build_full_history

                assert build_full_history(prevention_root, "learner")["accepted"] == 3
                cli.setattr(
                    public_prep_sys,
                    "argv",
                    [
                        "opening-profile",
                        "--project-root",
                        str(prevention_root),
                        "--game-id",
                        str(later_games[0][0]),
                        "--position-id",
                        str(later_games[0][1]),
                        "--alternative",
                        "f1c4",
                        "--reference",
                        "recent",
                        "--prepare-public-prevention",
                        "--fork-window",
                        "continuation",
                    ],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                prevention = json.loads(output.getvalue())
                assert prevention["version"] == "public-opening-fork-prevention-v1"
                assert prevention["prevention_policy"]["proofs_per_preparation"] == 32
                assert prevention["prevention_policy"]["window"] == "continuation"
                assert prevention["prevention_policy"]["proof_seconds"] == 20
                assert prevention["prevention_policy"]["shared_seconds"] == 30
                assert (
                    prevention["prevention_policy"]["index_sha256"]
                    == hashlib.sha256((prevention_planning / FULL_INDEX).read_bytes()).hexdigest()
                )
                assert (
                    prevention["reference"]["source_sha256"]
                    == hashlib.sha256(prevention_prefix).hexdigest()
                )
                from chess_coach.fact_fingerprint import canonical, digest

                for label, origin in (("played", "pre_existing"), ("alternative", "created")):
                    branch = prevention["branches"][label]
                    expected_games = 2 if label == "played" else 1
                    assert branch["selected"] == branch["eligible"] == expected_games
                    assert branch["origins"][origin]["supported"] == expected_games
                    for coverage in branch["origins"].values():
                        assert (
                            sum(
                                coverage[key]
                                for key in (
                                    "supported",
                                    "unsupported",
                                    "incomplete",
                                    "completed_without_example",
                                    "ended_before_window",
                                )
                            )
                            == branch["selected"]
                        )
                    example = branch["origins"][origin]["example"]
                    assert example["origin"] == (
                        "pre_existing" if origin == "pre_existing" else "created_by_recorded_move"
                    )
                    assert example["window_start"] == 39
                    assert example["window_end"] == example["ply"]
                    assert example["record_ended_in_window"]
                    assert example["board_terminal_at_record_end"] is None
                    assert example["response"]["status"] == "correct"
                    if origin == "pre_existing":
                        assert example["recorded_response_status"] == "unresolved"
                        assert example["alternative_uci"] != example["recorded_uci"]
                    else:
                        assert example["recorded_response_status"] == "not_assessed"
                    fixture = prevention_fixtures[origin]
                    history, recorded = fixture["history"], fixture["recorded"]
                    assert isinstance(history, list) and isinstance(recorded, str)
                    assert example["history_sha256"] == digest(canonical(history))
                    assert example["full_history_sha256"] == digest(canonical([*history, recorded]))
                assert 0 < prevention["branches"]["played"]["preparation_proofs"] <= 32

                # Exhausting the single preparation budget keeps both branches incomplete.
                from copy import deepcopy

                from chess_coach.opening_full_history_locate import locate as locate_full
                from chess_coach.opening_public_prevention import evaluate as evaluate_prevention

                prevention_artifact = next(prevention_planning.glob("opening-public-proof-*.json"))
                saved_binding = json.loads(prevention_artifact.read_text())["payload"]["binding"]
                identity = deepcopy(saved_binding)
                identity["policy"]["prevention"]["proofs_per_preparation"] = 0
                budget_start = time.monotonic()
                limited, _, _ = evaluate_prevention(
                    locate_full(prevention_root, "learner"),
                    identity,
                    budget_start,
                    budget_start + 20,
                )
                for branch in limited.values():
                    assert branch["selected"] > 0 and branch["proof_limit"]
                    assert branch["preparation_proofs"] == 0
                    assert all(
                        coverage["incomplete"] == branch["selected"]
                        for coverage in branch["origins"].values()
                    )
                # The initial operation is a distinct immutable result for the same pair.
                continuation_hash = hashlib.sha256(prevention_artifact.read_bytes()).hexdigest()
                cli.setattr(
                    public_prep_sys,
                    "argv",
                    [*public_prep_sys.argv[:-1], "initial"],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profile_cli.main()
                initial_prevention = json.loads(output.getvalue())
                assert initial_prevention["prevention_policy"]["window"] == "initial"
                assert initial_prevention["branches"]["played"]["selected"] == 2
                assert initial_prevention["branches"]["alternative"]["selected"] == 1
                initial_paths = set(prevention_planning.glob("opening-public-proof-*.json")) - {
                    prevention_artifact
                }
                assert len(initial_paths) == 1
                initial_artifact = initial_paths.pop()
                assert initial_artifact.stat().st_mode & 0o777 == 0o400
                initial_hash = hashlib.sha256(initial_artifact.read_bytes()).hexdigest()
                assert (
                    hashlib.sha256(prevention_artifact.read_bytes()).hexdigest()
                    == continuation_hash
                )

                # Replay the same selected source at its actual decision, then at a
                # later legal position to exercise the otherwise unreachable 52 frontier.
                from chess_coach.opening_public_fork_later_history import (
                    positions as fork_positions,
                )
                from chess_coach.opening_recent_select import rows as recent_rows

                full_source = locate_full(prevention_root, "learner")
                history_db = real_connect(
                    full_source[0].as_uri() + "?mode=ro&immutable=1", uri=True
                )
                try:
                    matches, _ = recent_rows(
                        history_db,
                        saved_binding["source"]["parent"],
                        saved_binding["source"]["played"],
                        saved_binding["ply"],
                        saved_binding["control"],
                    )
                    selected_history = next(row for row in matches if row[1] > 52)
                    _, moves, replay_rows, candidates, censored, safe = fork_positions(
                        history_db,
                        selected_history,
                        saved_binding,
                        saved_binding["source"]["played"],
                        time.monotonic() + 20,
                        window="initial",
                    )
                    assert safe and censored and replay_rows[-1][0] == 38
                    assert candidates[0][0] == 3 and candidates[-1][0] == 37
                    assert len(candidates[0][1].move_stack) == 2

                    late_board = chess.Board()
                    for uci in moves[:18]:
                        late_board.push_uci(uci)
                    late_binding = {
                        **saved_binding,
                        "ply": 19,
                        "color": "white",
                        "source": {
                            **saved_binding["source"],
                            "parent": position_key(late_board),
                        },
                    }
                    _, _, replay_rows, candidates, censored, safe = fork_positions(
                        history_db,
                        selected_history,
                        late_binding,
                        moves[18],
                        time.monotonic() + 20,
                        window="initial",
                    )
                    assert safe and censored and replay_rows[-1][0] == 52
                    assert candidates[0][0] == 19 and candidates[-1][0] == 51
                    assert len(candidates[0][1].move_stack) == 18
                finally:
                    history_db.close()
                cli.setenv("CHESS_DB", str(db_path))

                # Direct mate and material-fork certificates are distinct outcomes.
                from chess_coach.opening_public_fork_candidate import inspect as inspect_fork

                recorded_board = chess.Board()
                for san in supported_fork.split()[:18]:
                    recorded_board.push_san(san)
                recorded_move = recorded_board.parse_san("Qh5+")
                recorded_state, recorded_proof = inspect_fork(
                    recorded_board,
                    recorded_move,
                    recorded_move,
                    [],
                    1,
                    {"proofs": 0},
                    time.monotonic() + 30,
                )
                assert recorded_state == "material" and recorded_proof["recorded"]
                mate_board = chess.Board("7k/n7/5KQ1/8/8/8/8/8 w - - 0 1")
                mate_move = mate_board.parse_san("Qg7#")
                mate_state, mate_proof = inspect_fork(
                    mate_board, mate_move, mate_move, [], 1, {"proofs": 0}, time.monotonic() + 30
                )
                assert mate_state == "mate" and mate_proof["kind"] == "immediate_mate"
                assert mate_proof["proof"]["distance_plies"] == 1
                scoped_board = chess.Board()
                scoped_board.push_san("e4")
                scoped_move = scoped_board.parse_san("e5")
                scope_state, scope_proof = inspect_fork(
                    scoped_board,
                    scoped_move,
                    scoped_move,
                    [],
                    2,
                    {"proofs": 0},
                    time.monotonic() + 30,
                )
                assert scope_state == "scope" and scope_proof is None

                # Reopening the profile only reads prepared evidence; it runs no judge.
                import chess_coach.opening_public_fork_candidate as public_fork

                cli.setattr(public_replay, "judge", lambda *_a, **_k: pytest.fail("proof on GET"))
                cli.setattr(public_fork, "fork_proof", lambda *_a, **_k: pytest.fail("fork on GET"))
                shown = cli_profile(recent_root, "learner", *later_games[0], "f1c4", "recent")
                assert shown["public_preparation"]["branches"]["alternative"]["example"]
                assert shown["public_preparation"]["branches"]["played"]["forks"]["example"]
                assert shown["public_preparation"]["legacy_capture"]["alternative"]["example"]
                later_shown = cli_profile(
                    recent_root,
                    "learner",
                    *later_games[0],
                    "f1c4",
                    "recent",
                    fork_window="continuation",
                )
                assert later_shown["public_preparation"]["branches"]["played"]["forks"]["example"]
                full_index.chmod(0o600)
                try:
                    fallback_later = cli_profile(
                        recent_root,
                        "learner",
                        *later_games[0],
                        "f1c4",
                        "recent",
                        fork_window="continuation",
                    )
                    fallback_preparation = fallback_later["public_preparation"]
                    assert (
                        fallback_preparation["version"] == "public-opening-capture-preparation-v1"
                    )
                    assert "forks" not in fallback_preparation["branches"]["played"]
                    assert fallback_preparation["branches"]["alternative"]["example"]
                finally:
                    full_index.chmod(0o400)
                # Prevention profile reads the stored result without any proof work.
                import chess_coach.opening_public_prevention_created as prevention_created
                import chess_coach.opening_public_prevention_existing as prevention_existing

                cli.setattr(
                    prevention_existing,
                    "anchor",
                    lambda *_a, **_k: pytest.fail("prevention anchor on GET"),
                )
                cli.setattr(
                    prevention_created,
                    "scan",
                    lambda *_a, **_k: pytest.fail("prevention scan on GET"),
                )
                fallback_prevention = cli_profile(
                    recent_root,
                    "learner",
                    *later_games[0],
                    "f1c4",
                    "recent",
                    fork_window="continuation",
                    proof_kind="prevention",
                )
                assert (
                    fallback_prevention["public_preparation"]["prevention_status"] == "unavailable"
                )
                assert fallback_prevention["public_preparation"]["version"] == (
                    "public-opening-capture-preparation-v1"
                )
                cli.setenv("CHESS_DB", str(prevention_db_path))
                prevention_shown = cli_profile(
                    prevention_root,
                    "learner",
                    *later_games[0],
                    "f1c4",
                    "recent",
                    fork_window="continuation",
                    proof_kind="prevention",
                )
                assert prevention_shown["public_preparation"]["branches"]["played"]["origins"][
                    "pre_existing"
                ]["example"]
                initial_shown = cli_profile(
                    prevention_root,
                    "learner",
                    *later_games[0],
                    "f1c4",
                    "recent",
                    fork_window="initial",
                    proof_kind="prevention",
                )
                assert (
                    initial_shown["public_preparation"]["prevention_policy"]["window"] == "initial"
                )
                assert (
                    initial_shown["public_preparation"]["branches"]
                    == initial_prevention["branches"]
                )
                assert hashlib.sha256(initial_artifact.read_bytes()).hexdigest() == initial_hash
                assert (
                    hashlib.sha256(prevention_artifact.read_bytes()).hexdigest()
                    == continuation_hash
                )
                prevention_app = create_app(
                    db_path=prevention_db_path,
                    project_root=prevention_root,
                    subject="learner",
                    actor="reviewer",
                    corpus="test",
                    login="fixture",
                    origin="https://coach.invalid",
                )
                prevention_route = (
                    f"/repertoire/games/{later_games[0][0]}/openings/{later_games[0][1]}"
                    "/profile?reference=recent&alternative=f1c4"
                    "&fork_window=continuation&proof_kind=prevention"
                )
                prevention_page = prevention_app.test_client().get(
                    prevention_route,
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert prevention_page.status_code == 200
                assert b"Public prevention example" in prevention_page.data
                initial_page = prevention_app.test_client().get(
                    prevention_route.replace("continuation", "initial"),
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert initial_page.status_code == 200
                assert b"The initial window" in initial_page.data
                section = prevention_page.data.split(
                    b"<h3>Prepared public knight-fork prevention</h3>", 1
                )[1]
                summary = b"<summary>Source and analysis details</summary>"
                assert summary in section
                assert (
                    prevention["prevention_policy"]["index_sha256"].encode()
                    not in section.split(summary, 1)[0]
                )
                assert (
                    prevention["prevention_policy"]["index_sha256"].encode()
                    in section.split(summary, 1)[1]
                )
                missing_full = prevention_planning / FULL_INDEX
                missing_full.chmod(0o600)
                try:
                    unavailable_prevention = cli_profile(
                        prevention_root,
                        "learner",
                        *later_games[0],
                        "f1c4",
                        "recent",
                        fork_window="continuation",
                        proof_kind="prevention",
                    )
                    assert unavailable_prevention["public_preparation"] is None
                finally:
                    missing_full.chmod(0o400)
                assert (
                    hashlib.sha256(prevention_db_path.read_bytes()).hexdigest()
                    == prevention_db_hash
                )

                # Qualify real recorded defenses from separate standard-start public games.
                protection_root = tmp_path / "public-protection"
                protection_planning = protection_root / ".runtime" / "planning"
                protection_data = protection_root / ".runtime" / "data"
                protection_planning.mkdir(parents=True, mode=0o700)
                protection_data.mkdir(mode=0o700)
                protection_db_path = protection_data / "synthetic.sqlite"
                source_connection = real_connect(db_path)
                destination_connection = real_connect(protection_db_path)
                source_connection.backup(destination_connection)
                destination_connection.close()
                source_connection.close()
                with cli.context() as setup:
                    setup.setattr(sqlite3, "connect", real_connect)
                    protection_db = Database(protection_db_path)
                    black_pgn = (
                        '[Event "Protection fixture"]\n[White "synthetic opponent"]\n'
                        '[Black "learner"]\n[UTCDate "2026.01.02"]\n'
                        '[UTCTime "12:05:00"]\n[TimeControl "600+0"]\n[Result "*"]\n\n'
                        "1. e4 e5 2. Nc3 Nf6 3. d3 Bb4 4. a3 Ba5 *\n"
                    )
                    ingest_pgn(protection_db, black_pgn)
                    black_game = protection_db.connection.execute(
                        "SELECT max(id) FROM games"
                    ).fetchone()[0]
                    black_position = protection_db.connection.execute(
                        "SELECT id FROM positions WHERE game_id=? AND ply=2", (black_game,)
                    ).fetchone()[0]
                    classify_game(protection_db, black_game, version=VERSION, source_url=SOURCE)
                    protection_db.close()
                protection_hash = hashlib.sha256(protection_db_path.read_bytes()).hexdigest()
                histories = (
                    "e4 e5 Nf3 Nc6 Bb5 a6 Ba4",
                    "e4 e5 Bc4 Nc6 Bb5 a6 Ba4",
                    "e4 e5 Nc3 Nf6 d3 Bb4 a3 Ba5",
                    "e4 Nf6 Nc3 e5 d3 Bb4 a3 Ba5",
                )
                protection_text = "\n\n".join(
                    rated_game(index, 700 + index, "600+0", moves=moves)
                    for index, moves in enumerate(histories)
                )
                protection_zstd = subprocess.run(
                    ["/usr/bin/zstd", "-q", "-c"],
                    input=(protection_text + "\n\n{" + noise).encode(),
                    stdout=subprocess.PIPE,
                    check=True,
                ).stdout
                assert len(protection_zstd) > PREFIX_BYTES
                protection_prefix = protection_zstd[:PREFIX_BYTES]

                def protection_response(request):
                    return httpx.Response(
                        206,
                        headers={
                            "Content-Range": f"bytes 0-{PREFIX_BYTES - 1}/{PREFIX_BYTES * 2}",
                            "Content-Length": str(PREFIX_BYTES),
                            "ETag": '"synthetic-piece-protection"',
                        },
                        content=protection_prefix,
                        request=request,
                    )

                with httpx.Client(transport=httpx.MockTransport(protection_response)) as fake:
                    acquire(protection_root, "learner", client=fake)
                assert build_recent(protection_root, "learner")["accepted"] == 4
                cli.setenv("CHESS_DB", str(protection_db_path))
                decisions = (
                    (later_games[0], "f1c4", "white"),
                    ((black_game, black_position), "g8f6", "black"),
                )
                for (game_id, position_id), alternative, color in decisions:
                    absent = cli_profile(
                        protection_root,
                        "learner",
                        game_id,
                        position_id,
                        alternative,
                        "recent",
                        proof_kind="protection",
                    )
                    assert absent["public_preparation"] is None
                    cli.setattr(
                        public_prep_sys,
                        "argv",
                        [
                            "opening-profile",
                            "--project-root",
                            str(protection_root),
                            "--game-id",
                            str(game_id),
                            "--position-id",
                            str(position_id),
                            "--alternative",
                            alternative,
                            "--reference",
                            "recent",
                            "--prepare-public-protection",
                        ],
                    )
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        profile_cli.main()
                    public_protection = json.loads(output.getvalue())
                    assert public_protection["version"] == "public-opening-piece-protection-v1"
                    assert (
                        public_protection["protection_policy"]["verifier"]
                        == "threatened-piece-verifier-v1"
                    )
                    played = public_protection["branches"]["played"]
                    other = public_protection["branches"]["alternative"]
                    assert played["selected"] and other["selected"]
                    assert played["analyzed"] and other["analyzed"]
                    assert played["supported"] and other["supported"]
                    example = played["example"]
                    assert example["proof"]["status"] == "correct"
                    assert example["target"] == ("b5" if color == "white" else "b4")
                    assert example["recorded_san"] == ("Ba4" if color == "white" else "Ba5")
                    assert example["record_hash"]
                    from chess_coach.objective_short_history import history_hash
                    from chess_coach.opening_recent_source import INDEX_NAME as RECENT_INDEX

                    indexed = real_connect(
                        (protection_planning / RECENT_INDEX).as_uri() + "?mode=ro&immutable=1",
                        uri=True,
                    )
                    rows = indexed.execute(
                        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<? ORDER BY ply",
                        (example["record"], example["ply"]),
                    ).fetchall()
                    indexed.close()
                    assert example["history_sha256"] == digest(canonical(rows))
                    source_board = chess.Board()
                    for san in histories[0 if color == "white" else 2].split()[:-1]:
                        source_board.push_san(san)
                    assert example["proof"]["history_hash"] == history_hash(source_board)
                    assert (
                        public_protection["reference"]["source_sha256"]
                        == hashlib.sha256(protection_prefix).hexdigest()
                    )
                    shown_protection = cli_profile(
                        protection_root,
                        "learner",
                        game_id,
                        position_id,
                        alternative,
                        "recent",
                        proof_kind="protection",
                    )["public_preparation"]
                    assert shown_protection["branches"] == public_protection["branches"]
                    assert shown_protection["reference"]["license"] == "CC0-1.0"

                # An expired caller deadline interrupts the real verifier rather than judging a move.
                from chess_coach.objective_protection_before import probe as protection_probe
                from chess_coach.objective_protection_judge import judge as protection_judge

                white_board = chess.Board()
                for san in histories[0].split()[:-1]:
                    white_board.push_san(san)
                import chess_coach.material_exchange as material_exchange

                real_recaptures = material_exchange.recaptures
                entered, completed = [], []

                def tracked_recaptures(*args, **kwargs):
                    entered.append(True)
                    value = real_recaptures(*args, **kwargs)
                    completed.append(True)
                    return value

                def expire_protection():
                    if entered:
                        raise TimeoutError("synthetic protection deadline")

                with cli.context() as interruption:
                    interruption.setattr(material_exchange, "recaptures", tracked_recaptures)
                    with pytest.raises(TimeoutError, match="synthetic protection deadline"):
                        protection_judge(
                            white_board,
                            white_board.parse_san("Ba4"),
                            chess.B5,
                            time.monotonic,
                            time.monotonic(),
                            5,
                            {},
                            check=expire_protection,
                        )
                assert entered and not completed
                assert protection_probe(white_board)["targets"]
                import chess_coach.opening_public_protection_replay as public_protection_replay

                with cli.context() as no_proof:
                    no_proof.setattr(
                        public_protection_replay,
                        "probe",
                        lambda *_a, **_k: pytest.fail("proof on GET"),
                    )
                    no_proof.setattr(
                        public_protection_replay,
                        "judge",
                        lambda *_a, **_k: pytest.fail("proof on GET"),
                    )
                    app_protection = create_app(
                        db_path=protection_db_path,
                        project_root=protection_root,
                        subject="learner",
                        actor="reviewer",
                        corpus="test",
                        login="fixture",
                        origin="https://coach.invalid",
                    )
                    for (game_id, position_id), alternative, _color in decisions:
                        read_only = cli_profile(
                            protection_root,
                            "learner",
                            game_id,
                            position_id,
                            alternative,
                            "recent",
                            proof_kind="protection",
                        )
                        assert read_only["public_preparation"]["protection_status"] == "prepared"
                        page = app_protection.test_client().get(
                            f"/repertoire/games/{game_id}/openings/{position_id}/profile",
                            query_string={
                                "reference": "recent",
                                "alternative": alternative,
                                "proof_kind": "protection",
                            },
                            base_url="https://coach.invalid",
                            headers=headers,
                        )
                        assert page.status_code == 200
                        assert b"Public defense example" in page.data
                        assert b"do not establish mistakes" in page.data
                assert (
                    hashlib.sha256(protection_db_path.read_bytes()).hexdigest() == protection_hash
                )
                protection_file = protection_planning / PREFIX_NAME
                original = protection_file.read_bytes()
                protection_file.chmod(0o600)
                try:
                    with protection_file.open("r+b") as stream:
                        stream.write(bytes([original[0] ^ 1]))
                    stale = cli_profile(
                        protection_root,
                        "learner",
                        *later_games[0],
                        "f1c4",
                        "recent",
                        proof_kind="protection",
                    )
                    assert stale["public_preparation"] is None
                finally:
                    with protection_file.open("r+b") as stream:
                        stream.write(original[:1])
                    protection_file.chmod(0o400)
                assert protection_file.read_bytes() == original
                cli.setenv("CHESS_DB", str(db_path))
                profile_app = create_app(
                    db_path=db_path,
                    project_root=recent_root,
                    subject="learner",
                    actor="reviewer",
                    corpus="test",
                    login="fixture",
                    origin="https://coach.invalid",
                )
                profile_client = profile_app.test_client()
                profile_route = (
                    f"/repertoire/games/{later_games[0][0]}/openings/{later_games[0][1]}"
                    "/profile?reference=recent&alternative=f1c4"
                )
                page = profile_client.get(
                    profile_route, base_url="https://coach.invalid", headers=headers
                )
                assert (
                    page.status_code == 200 and b"Prepared public capture observations" in page.data
                )
                assert b"Public source example" in page.data
                assert b"Prepared fork opportunities" in page.data
                assert b"Public fork example" in page.data
                assert b"do not establish a mistake" in page.data
                later_page = profile_client.get(
                    profile_route + "&fork_window=continuation",
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert later_page.status_code == 200 and b"Public fork example" in later_page.data
                assert b"Full-history index" in later_page.data
                import copy

                partial = copy.deepcopy(shown["public_preparation"])
                partial["branches"]["played"]["analyzed"] = 0
                with cli.context() as fallback_view:
                    fallback_view.setattr(
                        profile_web, "prepared_proof", lambda *_args, **_kwargs: partial
                    )
                    page = profile_client.get(
                        profile_route, base_url="https://coach.invalid", headers=headers
                    )
                    assert b"Earlier capture-only preparation" in page.data
                    assert b"Public capture example" in page.data
                assert set(recent_planning.glob("opening-public-proof-*.json")) == artifact_names

                # A changed source prefix invalidates the prepared result, without replacement.
                prefix_path = recent_planning / PREFIX_NAME
                original_prefix = prefix_path.read_bytes()
                prefix_path.chmod(0o600)
                try:
                    with prefix_path.open("r+b") as stream:
                        stream.write(bytes([original_prefix[0] ^ 1]))
                    unavailable = cli_profile(
                        recent_root, "learner", *later_games[0], "f1c4", "recent"
                    )
                    assert unavailable["public_preparation"] is None
                finally:
                    with prefix_path.open("r+b") as stream:
                        stream.write(original_prefix[:1])
                    prefix_path.chmod(0o400)
                assert prefix_path.read_bytes() == original_prefix
                assert set(recent_planning.glob("opening-public-proof-*.json")) == artifact_names
            assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before

            # Two independently identified original games share the actual
            # catalog branch and contain current detector-backed fork misses.
            from chess_coach import cli as nomination_cli
            from chess_coach.evidence_review import review_evidence
            from chess_coach.fork_detector import process_decision
            from chess_coach.opening_decision import inspect as inspect_opening
            from chess_coach.opening_explore import explore as explore_opening
            from chess_coach.opening_explore_view import report as exploration_report
            from chess_coach.opening_public_proof import prepare as prepare_fork_proof
            from chess_coach.pipeline_config import PipelineConfig
            from chess_coach.pipeline_inputs import engine_identity, game_input
            from chess_coach.pipeline_work import run_analysis

            class NominationEngine:
                def __init__(self):
                    self.id = {"name": "synthetic fork fixture"}
                    self.options = {}

                def configure(self, _settings):
                    pass

                def quit(self):
                    pass

                def analyse(self, board, limit, multipv, root_moves=None):
                    if len(board.move_stack) == 22:
                        pv = "d1g4 g8e7" if root_moves else "d1h5 f7g7 h5h3 g8e7"
                        score = 0 if root_moves else 300
                        moves = [chess.Move.from_uci(move) for move in pv.split()]
                    else:
                        move = root_moves[0] if root_moves else next(iter(board.legal_moves))
                        replay = board.copy()
                        replay.push(move)
                        moves = [move]
                        if not replay.is_game_over():
                            moves.append(next(iter(replay.legal_moves)))
                        score = 0
                    return [
                        {
                            "pv": moves,
                            "score": chess.engine.PovScore(chess.engine.Cp(score), board.turn),
                            "nodes": 100,
                            "depth": 5,
                        }
                    ]

            nomination_path = data / "nomination.sqlite"
            nomination_db = Database(nomination_path)
            nomination_db.initialize()
            import_snapshot(nomination_db)
            evidence_ids, fork_positions = [], []
            with patch.context() as own_engine:
                own_engine.setattr(
                    chess.engine.SimpleEngine, "popen_uci", lambda *_args: NominationEngine()
                )
                for index in range(3):
                    original = chess.pgn.Game()
                    original.headers.update(
                        White="learner",
                        Black=f"fork-opponent-{index}",
                        Result="*",
                        TimeControl="1800+0",
                        UTCDate="2026.01.02",
                        UTCTime=f"12:02:0{index}",
                    )
                    board, node = original.board(), original
                    for san in nomination_fork.split():
                        move = board.parse_san(san)
                        node = node.add_variation(move)
                        board.push(move)
                    ingest_pgn(nomination_db, str(original))
                    game_id = nomination_db.connection.execute(
                        "SELECT MAX(id) FROM games"
                    ).fetchone()[0]
                    classify_game(nomination_db, game_id, version=VERSION, source_url=SOURCE)
                    config = PipelineConfig(
                        learner="learner", engine_path=sys.executable, nodes=100, deep_enabled=False
                    )
                    analysis = run_analysis(
                        nomination_db,
                        game_id,
                        game_input(nomination_db, game_id),
                        config,
                        engine_identity(sys.executable),
                    )
                    assert analysis["status"] == "complete"
                    fork_position = nomination_db.connection.execute(
                        "SELECT id FROM positions WHERE game_id=? AND ply=23", (game_id,)
                    ).fetchone()[0]
                    fork_positions.append(fork_position)
            nomination_db.connection.commit()

            # Three separate owned games have an actual central pawn-capture
            # decision after the repeated branch; each uses a current same-search
            # purpose comparison rather than a synthesized style conclusion.
            from chess_coach.style_history_lines import history_safe

            def nomination_center(_db, snapshot, _config, _deadline):
                board, position = snapshot["board"], snapshot["position"]
                roots = [chess.Move.from_uci(position["uci"]), board.parse_san("d3")]
                raw = []
                for root in roots:
                    replay, pv = board.copy(), [root]
                    replay.push(root)
                    for _ in range(3):
                        move = next(
                            move
                            for move in replay.legal_moves
                            if not move.promotion and history_safe(_after(replay, move))
                        )
                        pv.append(move)
                        replay.push(move)
                    raw.append(
                        {
                            "pv": pv,
                            "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                            "nodes": 500,
                            "depth": 5,
                            "time": 0.05,
                        }
                    )
                lines, invalid = native(position, board, raw)
                assert not invalid
                return (
                    "complete",
                    "comparable",
                    {
                        "scout": {"lines": lines},
                        "final": {"lines": lines, "roots": [move.uci() for move in roots]},
                        "engine": {},
                        "runtime_engine": {},
                    },
                )

            def _after(board, move):
                result = board.copy()
                result.push(move)
                return result

            with patch.context() as center_engine:
                center_engine.setattr(purpose_worker, "execute", nomination_center)
                for index, position in enumerate(fork_positions):
                    game_id = nomination_db.connection.execute(
                        "SELECT game_id FROM positions WHERE id=?", (position,)
                    ).fetchone()[0]
                    center_id = nomination_db.connection.execute(
                        "SELECT id FROM positions WHERE game_id=? AND ply=13", (game_id,)
                    ).fetchone()[0]
                    request_id = create(
                        nomination_db, center_id, "learner", engine_path=sys.executable
                    )["request_id"]
                    assert (
                        purpose_worker.run(nomination_db, request_id, "learner")["status"]
                        == "complete"
                    )
                    cycle = nomination_db.connection.execute(
                        "INSERT INTO style_schedule_cycles(learner_key,sequence,coverage_json) VALUES(?,?,?)",
                        (
                            learner_key("learner"),
                            501 + 4 * index,
                            json.dumps(
                                {
                                    "early_center_policy": "early-center-v1",
                                    "early_center_targeted": True,
                                }
                            ),
                        ),
                    ).lastrowid
                    nomination_db.connection.execute(
                        "INSERT INTO style_schedule_slots(cycle_id,kind,game_id,position_id,status,detail,request_id) VALUES(?,?,?,?,?,?,?)",
                        (cycle, "control", game_id, center_id, "complete", "fixture", request_id),
                    )
                    nomination_db.connection.commit()
            sparse = exploration_report(
                nomination_db, recent_root, "learner", fork=True, revision=True
            )
            assert sparse["fork_nomination"]["reason"] == "fewer_than_two_independent_miss_games"
            assert sparse["revision_judgments"]["reason"] == "current_fork_nomination_unavailable"
            for fork_position in fork_positions[:2]:
                observed = process_decision(nomination_db, fork_position, "learner")
                assert observed["outcome"] == "failure"
                evidence_ids.append(observed["evidence_ids"][0])
            exploration = explore_opening(nomination_db, "learner")
            assert exploration["branch"]["exemplar"]["ply"] == 5
            exemplar = exploration["branch"]["exemplar"]
            selected = inspect_opening(
                nomination_db, exemplar["game_id"], exemplar["position_id"], "learner"
            )
            alternative = selected["catalog"]["items"][0]["uci"]

            missing = exploration_report(nomination_db, recent_root, "learner", fork=True)
            assert missing["fork_nomination"]["reason"] == "current_public_fork_unavailable"
            source = prepare_fork_proof(
                nomination_db,
                recent_root,
                "learner",
                exemplar["game_id"],
                exemplar["position_id"],
                alternative,
                forks=True,
            )
            assert source["branches"]["played"]["forks"]["example"]["kind"] == "material"
            assert source["branches"]["played"]["forks"]["censored"] == 1

            # The independent center observations and public windows support
            # the played branch in one pair; a different candidate has its
            # own material fork certificate in the same source-bound decision.
            revision_decision = {**exemplar, "color": exploration["branch"]["color"]}
            revision_choices = {item["uci"]: item for item in selected["catalog"]["items"]}
            fitted = later_assess(
                nomination_db,
                recent_root,
                "learner",
                revision_decision,
                revision_choices["f3e5"],
                source="recent",
            )
            assert fitted["owned"]["branches"][exemplar["played_uci"]]["games"] == 3
            assert fitted["recommended"] == exemplar["played_uci"]
            alternate_fork = prepare_fork_proof(
                nomination_db,
                recent_root,
                "learner",
                exemplar["game_id"],
                exemplar["position_id"],
                "b1c3",
                forks=True,
            )
            assert (
                alternate_fork["branches"]["alternative"]["forks"]["example"]["kind"] == "material"
            )

            # Persist synthetic full-root measurements through the native
            # collector and source-bound artifact format; the judgments are
            # computed by the production readers and admission rules.
            import chess_coach.opening_queue_artifact as revision_artifact
            import chess_coach.opening_queue_binding as revision_binding
            from chess_coach.opening_measure_prepare import _envelope as revision_envelope
            from chess_coach.opening_measure_reference import ReferenceIterations
            from chess_coach.opening_queue_location import location as revision_location
            from chess_coach.opening_queue_proof import complete as reference_complete

            patch.setattr(revision_binding, "ENGINE", sys.executable)
            directory, database_key = revision_location(nomination_db, recent_root, "learner")
            for choice_move in ("f3e5", "b1c3", "b2b4"):
                _, binding, config, position = revision_binding.snapshot(
                    nomination_db,
                    database_key,
                    "learner",
                    exemplar["game_id"],
                    exemplar["position_id"],
                    choice_move,
                )
                board = position["board"]
                roots = sorted(
                    board.legal_moves, key=lambda move: (move.uci() == "b2b4", move.uci())
                )
                iteration = ReferenceIterations(board, position["position"], roots, (1, 64, 3))
                for rank_number, root in enumerate(roots, 1):
                    replay, pv = board.copy(), [root]
                    replay.push(root)
                    for _ in range(2):
                        following = next(
                            move
                            for move in replay.legal_moves
                            if not move.promotion and history_safe(_after(replay, move))
                        )
                        pv.append(following)
                        replay.push(following)
                    iteration.add(
                        {
                            "multipv": rank_number,
                            "depth": 5,
                            "pv": pv,
                            "score": chess.engine.PovScore(
                                chess.engine.Cp(-100 if root.uci() == "b2b4" else 0), board.turn
                            ),
                            "nodes": 10000,
                            "time": 0.1,
                        }
                    )
                outcome = {
                    "status": "complete",
                    "policy": "all-legal-roots-v2",
                    "lines": [{"rank": item["rank"], **item["line"]} for item in iteration.best],
                    "work": {
                        "nodes": 10000,
                        "time_seconds": 0.1,
                        "node_limit_exceeded": False,
                        "requested_nodes": 180000,
                    },
                    "retained_depth": 5,
                    "effective_multipv": len(roots),
                    "multipv_max": len(roots),
                }
                assert reference_complete(outcome, binding, board, reference=True)
                request = revision_binding.request(database_key, binding, config)
                artifact = revision_artifact.path(directory, request)
                artifact.write_text(json.dumps(revision_envelope(binding, config, outcome)))
                artifact.chmod(0o600)

            # A valid earlier two-root rehearsal remains readable but cannot
            # establish an all-root reference for the new judgment.
            _, binding, config, position = revision_binding.snapshot(
                nomination_db,
                database_key,
                "learner",
                exemplar["game_id"],
                exemplar["position_id"],
                "f1b5",
            )
            previous_config = revision_binding.legacy_config(config)
            previous = {
                "status": "complete",
                "work": outcome["work"],
                "lines": [
                    line for line in outcome["lines"] if line["root_move"] in {"f1c4", "f1b5"}
                ],
            }
            assert reference_complete(previous, binding, position["board"])
            request = revision_binding.request(database_key, binding, previous_config)
            artifact = revision_artifact.path(directory, request)
            artifact.write_text(json.dumps(revision_envelope(binding, previous_config, previous)))
            artifact.chmod(0o600)
            from chess_coach.opening_explore_alternatives import describe as describe_alternatives
            from chess_coach.opening_queue_view import statuses as comparison_statuses

            comparisons = comparison_statuses(nomination_db, recent_root, "learner", exemplar)
            existing = {
                item["choice"]["uci"]: item for item in describe_alternatives(exemplar, comparisons)
            }
            assert existing["f1b5"]["status"] == "complete" and existing["f1b5"]["ready"]

            # Unrelated ambiguous history must not exhaust the selected-game scan.
            from chess_coach.recurrence_sources import evidence as recurrence_evidence

            ambient = chess.pgn.Game()
            ambient.headers.update(
                White="learner",
                Black="ambient-opponent",
                Result="*",
                UTCDate="2026.01.02",
                UTCTime="12:03:00",
                TimeControl="1800+0",
            )
            ambient_node = ambient.add_variation(chess.Move.from_uci("d2d4"))
            ambient_node.add_variation(chess.Move.from_uci("d7d5"))
            ingest_pgn(nomination_db, str(ambient))
            ambient_position = nomination_db.connection.execute(
                "SELECT id FROM positions WHERE game_id=(SELECT MAX(id) FROM games) AND ply=1"
            ).fetchone()[0]
            nomination_db.connection.executemany(
                "INSERT INTO evidence_mappings(position_id,skill,operation,outcome,confidence,subject) "
                "VALUES(?,'fork','execute','ambiguous',0,'learner')",
                [(ambient_position,)] * 301,
            )
            nomination_db.connection.commit()
            global_rows, truncated = recurrence_evidence(
                nomination_db, "learner", "fork", "execute", (1 << 63) - 1
            )
            assert truncated and len(global_rows) == 300
            # Give the selected course a distinct licensed broadcast continuation.
            broadcast = recent_planning / SOURCE_NAME
            broadcast.write_bytes(b"synthetic selected revision archive")
            public_game = rated_game(0, 501, "1800+0", moves=fork_alternative)
            with patch.context() as broadcast_source:
                broadcast_source.setattr(reference_source, "SOURCE_BYTES", broadcast.stat().st_size)
                broadcast_source.setattr(
                    reference_source,
                    "SOURCE_SHA256",
                    hashlib.sha256(broadcast.read_bytes()).hexdigest(),
                )
                broadcast_source.setattr(
                    reference_source, "_decode", lambda _file: (public_game.encode(), False)
                )
                assert build_previous(recent_root, "learner")["accepted"] == 1
            nomination_hash = hashlib.sha256(nomination_path.read_bytes()).hexdigest()
            with patch.context() as checked_read:
                checked_read.setenv("CHESS_DB", str(nomination_path))
                checked_read.setenv("CHESS_SUBJECT", "learner")
                checked_read.delenv("CHESS_SCHEMA_COMPAT", raising=False)
                checked_read.setattr(
                    public_fork, "fork_proof", lambda *_a, **_k: pytest.fail("proof on GET")
                )
                checked_read.setattr(
                    public_replay, "judge", lambda *_a, **_k: pytest.fail("judge on GET")
                )
                checked_read.setattr(
                    sys,
                    "argv",
                    [
                        "chess-coach",
                        "--db",
                        str(nomination_path),
                        "repertoire",
                        "--learner",
                        "learner",
                        "--project-root",
                        str(recent_root),
                        "--fork-nominations",
                    ],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    nomination_cli.main()
                joined = json.loads(output.getvalue())["nomination"]
                assert joined["status"] == "provisional" and joined["miss_games"] == 2
                checked_read.setattr(
                    sys,
                    "argv",
                    [
                        "chess-coach",
                        "--db",
                        str(nomination_path),
                        "repertoire",
                        "--learner",
                        "learner",
                        "--project-root",
                        str(recent_root),
                        "--revision-judgments",
                    ],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    nomination_cli.main()
                revision = json.loads(output.getvalue())["judgments"]
                assert revision["status"] == "checked"
                assert revision["fit"]["winner"] == exemplar["played_uci"]
                assert revision["development"]["winner"] == "b1c3"
                assert revision["development"]["provisional"] is True
                revisions = {row["choice"]["uci"]: row for row in revision["alternatives"]}
                assert revisions["f3e5"]["admission"]["status"] == "eligible"
                assert (
                    revisions["f3e5"]["preparation"]["version"]
                    == "opening-preparation-inventory-v1"
                )
                assert revisions["f3e5"]["preparation"]["history"]["checked_games"] >= 1
                assert revision["owned_style"]["branches"][exemplar["played_uci"]]["games"] == 3
                assert revision["public_style"]["f3e5"]["available"] == 0
                assert revisions["b1c3"]["development"]["status"] == "provisional"
                assert revisions["b2b4"]["admission"]["status"] == "rejected"
                assert revisions["f1b5"]["admission"]["reason"] == "all_root_reference_unavailable"
                nomination_app = create_app(
                    db_path=nomination_path,
                    project_root=recent_root,
                    subject="learner",
                    actor="reviewer",
                    corpus="test",
                    login="fixture",
                    origin="https://coach.invalid",
                )
                page = nomination_app.test_client().get(
                    "/repertoire/explore?fork_nomination=1",
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert page.status_code == 200 and b"2 independently identified games" in page.data
                assert b"provisional pattern" in page.data and b"CC0-1.0" in page.data
                assert b"<summary>Source coverage</summary>" in page.data
                assert b"nominal time control was 1800+0" in page.data
                assert b"censored: 1" in page.data
                assert b"Public coverage is limited or unknown" in page.data
                assert b"do not establish that the opening caused" in page.data
                revision_page = nomination_app.test_client().get(
                    "/repertoire/explore?fork_nomination=revision",
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert revision_page.status_code == 200
                assert b"Compare revision possibilities" in revision_page.data
                assert b"Fit-eligible choices" in revision_page.data
                assert b"Development-eligible choices" in revision_page.data
                assert b"not a global ranking" in revision_page.data
                assert b"provisional learning experiment" in revision_page.data

                # Restore actual file-backed readers for the selected course;
                # the earlier first-turn fixture uses an in-memory index.
                import chess_coach.opening_fit_later_index as actual_later_index
                import chess_coach.opening_full_history_locate as actual_full_index

                checked_read.setattr(sqlite3, "connect", real_connect)
                checked_read.setattr(coursepublic, "planning", real_course_planning)
                checked_read.setattr(coursepublic, "_identity", real_course_identity)
                checked_read.setattr(coursepublic, "_private_file", real_course_private)
                checked_read.setattr(actual_later_index, "_identity", real_course_identity)
                checked_read.setattr(actual_later_index, "_private_file", real_course_private)
                checked_read.setattr(actual_full_index, "_identity", real_course_identity)
                checked_read.setattr(actual_full_index, "_private_file", real_course_private)

                # The selected recommendation is a new immutable version of
                # the normal course, preserving the prior preview and PGN.
                import chess_coach.ops_opening_profile as selected_cli
                import chess_coach.web_opening_course as selected_web
                from chess_coach.opening_recommendation_preview import (
                    legacy as legacy_recommendation,
                )
                from chess_coach.opening_recommendation_preview import (
                    preview as recommendation_preview,
                )
                from chess_coach.opening_recommendation_roles import (
                    version as recommendation_version,
                )
                from chess_coach.opening_revision_course import preview as legacy_preview
                from chess_coach.opening_revision_roles import three_roles as direct_roles
                from chess_coach.opening_study_course import build as build_study
                from chess_coach.opening_study_current import admitted as admitted_study
                from chess_coach.opening_study_source import fingerprint as source_fingerprint

                game_id, decision_id = exemplar["game_id"], exemplar["position_id"]
                legacy = legacy_preview(
                    nomination_db, recent_root, "learner", game_id, decision_id, "b1c3"
                )
                assert legacy["public_status"] == "available"
                old_recommendation = legacy_recommendation(
                    nomination_db, recent_root, "learner", game_id, decision_id, "b1c3"
                )
                direct_course = direct_roles(legacy)
                selected_course = recommendation_preview(
                    nomination_db,
                    recent_root,
                    "learner",
                    game_id,
                    decision_id,
                    "b1c3",
                    with_identity=True,
                )
                assert old_recommendation["schema"] == "opening-revision-course-v2"
                assert selected_course["schema"] == "opening-revision-course-v4"
                assert selected_course["source_version"] == old_recommendation["version"]
                assert (
                    selected_course["version"] != old_recommendation["version"] != legacy["version"]
                )
                assert [chapter["kind"] for chapter in selected_course["chapters"]] == [
                    "explanation",
                    "owned",
                    "public",
                ]
                assert selected_course["chapters"][1] == legacy["chapters"][0]
                assert "ungraded" in selected_course["chapters"][2]["pgn"]
                assert "CC BY-SA 4.0" in selected_course["chapters"][2]["pgn"]
                assert (
                    build_study(
                        direct_course, direct_course["version"], game_id, decision_id, "b1c3"
                    )["course"]["preview_version"]
                    == direct_course["version"]
                )
                mixed = {**selected_course, "chapters": list(reversed(selected_course["chapters"]))}
                mixed["version"] = recommendation_version(
                    mixed["source_version"], mixed["chapters"], mixed["rationale"]
                )
                with pytest.raises(ValueError):
                    build_study(mixed, mixed["version"], game_id, decision_id, "b1c3")
                assert selected_course["rationale"]["selected"] == "b1c3"
                assert selected_course["rationale"]["judgments"]["development"]["provisional"]
                assert "Selected by the learner" in selected_course["chapters"][0]["pgn"]
                assert (
                    "Public example after the recorded branch"
                    in selected_course["chapters"][0]["pgn"]
                )
                assert (
                    "Public example after the selected alternative"
                    in selected_course["chapters"][0]["pgn"]
                )
                assert "CC0-1.0" in selected_course["chapters"][0]["pgn"]
                with pytest.raises(ValueError):
                    recommendation_preview(
                        nomination_db, recent_root, "learner", game_id, decision_id, "b2b4"
                    )
                checked_read.setattr(
                    sys,
                    "argv",
                    [
                        "opening-profile",
                        "--project-root",
                        str(recent_root),
                        "--game-id",
                        str(game_id),
                        "--position-id",
                        str(decision_id),
                        "--alternative",
                        "b1c3",
                        "--recommendation-course",
                    ],
                )
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    selected_cli.main()
                assert json.loads(output.getvalue())["version"] == selected_course["version"]
                checked_read.setattr(selected_web, "record", lambda *_args, **_kwargs: None)
                selected_path = f"/repertoire/games/{game_id}/openings/{decision_id}/experiment/b1c3/course?recommendation=1"
                selected_client = nomination_app.test_client()
                selected_page = selected_client.get(
                    selected_path, base_url="https://coach.invalid", headers=headers
                )
                assert (
                    selected_page.status_code == 200
                    and b"Why this line is available" in selected_page.data
                )
                assert b"provisional developmental evidence" in selected_page.data
                assert b"Public example after the selected alternative" in selected_page.data
                assert b"1. Why study this position" in selected_page.data
                assert b"2. Your worked comparison" in selected_page.data
                assert b"3. Public continuation" in selected_page.data
                download = selected_client.get(
                    selected_path + "&download=1&version=" + selected_course["version"],
                    base_url="https://coach.invalid",
                    headers=headers,
                )
                assert download.status_code == 200 and b"Selected by the learner" in download.data
                assert download.get_data(as_text=True) == (
                    "\n\n".join(chapter["pgn"] for chapter in selected_course["chapters"]) + "\n"
                )
                assert (
                    legacy_preview(
                        nomination_db, recent_root, "learner", game_id, decision_id, "b1c3"
                    )
                    == legacy
                )

                with admitted_study(
                    nomination_path,
                    recent_planning,
                    recent_root,
                    "learner",
                    game_id,
                    decision_id,
                    "b1c3",
                    legacy["version"],
                    browser=True,
                ) as (legacy_study, _budget, check):
                    assert legacy_study["course"]["preview_version"] == legacy["version"]
                    check()

                with admitted_study(
                    nomination_path,
                    recent_planning,
                    recent_root,
                    "learner",
                    game_id,
                    decision_id,
                    "b1c3",
                    old_recommendation["version"],
                    browser=True,
                ) as (old_study, _budget, check):
                    assert old_study["course"]["preview_version"] == old_recommendation["version"]
                    assert len(old_study["course"]["chapters"]) == 2
                    check()

                # Even an absent watched proof attempt becoming present must
                # invalidate the exact course before a Study action proceeds.
                absent = next(
                    path
                    for path in selected_course["_paths"]
                    if path.name.startswith("opening-public-proof-") and not path.exists()
                )
                with admitted_study(
                    nomination_path,
                    recent_planning,
                    recent_root,
                    "learner",
                    game_id,
                    decision_id,
                    "b1c3",
                    selected_course["version"],
                    browser=True,
                ) as (study_course, _budget, check):
                    assert study_course["course"]["preview_version"] == selected_course["version"]
                    assert [item["kind"] for item in study_course["course"]["chapters"]] == [
                        "explanation",
                        "owned",
                        "public",
                    ]
                    before_paths = source_fingerprint(selected_course["_paths"])
                    try:
                        absent.write_text("{}")
                        absent.chmod(0o400)
                        assert source_fingerprint(selected_course["_paths"]) != before_paths
                        with pytest.raises(ValueError, match="source changed"):
                            check()
                    finally:
                        absent.unlink()
            assert hashlib.sha256(nomination_path.read_bytes()).hexdigest() == nomination_hash
            import chess_coach.opening_fork_nomination_source as nomination_source

            original_lookup = nomination_source.lookup

            def missing_censor(*args, **kwargs):
                result = original_lookup(*args, **kwargs)
                if result is not None:
                    forks = result["branches"]["played"].get("forks", {})
                    forks.pop("censored", None)
                return result

            with patch.context() as incomplete:
                incomplete.setattr(nomination_source, "lookup", missing_censor)
                uncertain = exploration_report(nomination_db, recent_root, "learner", fork=True)
                assert uncertain["fork_nomination"]["status"] == "provisional"
                assert uncertain["fork_nomination"]["source"]["coverage_complete"] is False
                assert uncertain["fork_nomination"]["source"]["example"]["proof"]["branches"]

            def missing_reply(*args, **kwargs):
                result = original_lookup(*args, **kwargs)
                if result is not None:
                    forks = result["branches"]["played"].get("forks", {})
                    example = forks.get("example")
                    if example:
                        example["proof"]["branches"].pop()
                return result

            with patch.context() as incomplete:
                incomplete.setattr(nomination_source, "lookup", missing_reply)
                unavailable = exploration_report(nomination_db, recent_root, "learner", fork=True)
                assert unavailable["fork_nomination"]["reason"] == "current_public_fork_unavailable"
            prefix_path.chmod(0o600)
            try:
                with prefix_path.open("r+b") as stream:
                    stream.write(bytes([original_prefix[0] ^ 1]))
                stale = exploration_report(
                    nomination_db, recent_root, "learner", fork=True, revision=True
                )
                assert stale["fork_nomination"]["reason"] == "current_public_fork_unavailable"
                assert (
                    stale["revision_judgments"]["reason"] == "current_fork_nomination_unavailable"
                )
                with pytest.raises(ValueError):
                    recommendation_preview(
                        nomination_db, recent_root, "learner", game_id, decision_id, "b1c3"
                    )
            finally:
                with prefix_path.open("r+b") as stream:
                    stream.write(original_prefix[:1])
                prefix_path.chmod(0o400)
            for evidence_id in evidence_ids:
                review_evidence(nomination_db, evidence_id, decision="accept", actor="fixture")
            accepted = exploration_report(nomination_db, recent_root, "learner", fork=True)
            assert accepted["fork_nomination"]["status"] == "provisional"
            assert accepted["fork_nomination"]["review"]["accepted"] == 2
            accepted_page = nomination_app.test_client().get(
                "/repertoire/explore?fork_nomination=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
            assert b"The included observations have accepted reviews" in accepted_page.data
            assert b"Some observations are unreviewed" not in accepted_page.data
            assert b"Public coverage is limited or unknown" in accepted_page.data
            review_evidence(nomination_db, evidence_ids[0], decision="revoke", actor="fixture")
            withheld = exploration_report(nomination_db, recent_root, "learner", fork=True)
            assert withheld["fork_nomination"]["status"] == "withheld"
            nomination_db.close()

    finally:
        public.close()
        owned.close()
