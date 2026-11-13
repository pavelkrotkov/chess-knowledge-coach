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
    assert cli_report["version"] == "style-choices-v13"
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


def test_duplicate_imports_do_not_count_as_independent_games(monkeypatch):
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

    def padded_game(event, prefix):
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
        moves = prefix + ["g8f6", "g1f3", "f6g8", "f3g1"] * 30
        for text in moves[:120]:
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
    _opening_fit_route(monkeypatch)


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


def _opening_fit_route(monkeypatch):
    """A normal choices request admits current owned evidence and public windows in memory."""
    import html
    import re
    import sqlite3
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
            assert (owned.connection.total_changes, public.total_changes) == before

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
    finally:
        public.close()
        owned.close()
