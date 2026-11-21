"""A successful defense leads to a source-bound, playable transfer."""

import json
import re
import sqlite3
import sys
from unittest.mock import Mock

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.related_protection import preview
from chess_coach.related_protection_features import protection_features
from chess_coach.related_protection_screen import plausible
from chess_coach.related_protection_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.test_material_pipeline import LEARNER, make_protection_game


def _guard_inspection_workflow(tmp_path, monkeypatch, capsys):
    import time

    import chess.engine
    import chess.pgn

    from chess_coach.cli import main
    from chess_coach.db import Database
    from chess_coach.ingest import ingest_pgn
    from chess_coach.objective_protection_judge import judge
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.style_guard_exchange import assess
    from chess_coach.style_guard_inspect import inspect
    from tests.test_material_pipeline import Engine

    initial = chess.Board("k7/8/8/5n2/3B4/8/7K/2R5 w - - 0 1")
    for color in ("white", "black"):
        board = initial.copy() if color == "white" else initial.mirror()

        def orient(text, color=color):
            move = chess.Move.from_uci(text)
            if color == "black":
                move = chess.Move(
                    chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
                )
            return move.uci()

        away, reply, guard, losing = map(orient, ("d4c3", "a8a7", "c1c4", "c1b1"))
        target = chess.D4 if color == "white" else chess.D5
        assert (
            judge(board, board.parse_uci(guard), target, time.monotonic, time.monotonic(), 5, {})[
                "status"
            ]
            == "unresolved"
        )
        assert (
            judge(board, board.parse_uci(away), target, time.monotonic, time.monotonic(), 5, {})[
                "status"
            ]
            == "correct"
        )
        game = chess.pgn.Game()
        game.setup(board)
        game.headers["White"] = LEARNER if color == "white" else "fixture_opponent"
        game.headers["Black"] = LEARNER if color == "black" else "fixture_opponent"
        game.headers["Result"] = "*"
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
        node = game.add_variation(board.parse_uci(away))
        continued = board.copy()
        continued.push_uci(away)
        node.add_variation(continued.parse_uci(reply))
        path = tmp_path / ("guard-" + color + ".sqlite")
        db = Database(path)
        db.initialize()
        ingest_pgn(db, str(game))
        monkeypatch.setattr(
            chess.engine.SimpleEngine,
            "popen_uci",
            lambda _, away=away, reply=reply: Engine(away, reply),
        )
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        assert (
            run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
        evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
        result = inspect(db, LEARNER, evidence, guard)
        assert result["status"] == "supported" and result["opponent_gain_max"] == 0
        assert result["guard_witness"] == {
            "capture": orient("f5d4"),
            "recapture": orient("c4d4"),
            "opponent_gain_max": 0,
        }
        assert result["target_captures"] == {"available": 1, "examined": 1}
        assert result["captures"] == [
            {
                "capture": orient("f5d4"),
                "opponent_gain": 0,
                "recapture": orient("c4d4"),
                "recapture_gain_max": 0,
            }
        ]
        assert result["source"]["history_mode"] == "owned_historical"
        assert 0 < result["coverage"]["exchange_nodes"] <= 64
        assert result["limits"]["deadline_seconds"] == 8.0
        alternative = inspect(db, LEARNER, evidence, away)
        assert alternative["status"] == "supported" and alternative["guard_witness"] is None
        assert inspect(db, LEARNER, evidence, losing)["status"] == "unknown"
        assert inspect(db, "other-owner", evidence, guard)["status"] == "unknown"
        with monkeypatch.context() as limited:
            limited.setattr("chess_coach.style_guard_inspect.NODE_LIMIT", 1)
            unfinished = inspect(db, LEARNER, evidence, guard)
            assert unfinished["status"] == "unknown" and unfinished["reason"] == "work_limit"
            assert unfinished["coverage"]["exchange_nodes"] <= 1
        with monkeypatch.context() as expired:
            expired.setattr("chess_coach.style_guard_inspect.SECONDS", 0.0)
            assert inspect(db, LEARNER, evidence, guard)["status"] == "unknown"
        counts = tuple(
            db.connection.execute(
                "SELECT (SELECT count(*) FROM evidence_mappings), (SELECT count(*) FROM training_attempts)"
            ).fetchone()
        )
        db.close()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "chess-coach",
                "--db",
                str(path),
                "style-choices",
                "--learner",
                LEARNER,
                "--protection-evidence",
                str(evidence),
                "--response",
                guard,
            ],
        )
        main()
        cli = json.loads(capsys.readouterr().out)
        assert (
            cli["version"] == "protection-exchange-inspection-v1"
            and cli["guard_witness"] == result["guard_witness"]
        )
        db = Database(path)
        assert (
            tuple(
                db.connection.execute(
                    "SELECT (SELECT count(*) FROM evidence_mappings), (SELECT count(*) FROM training_attempts)"
                ).fetchone()
            )
            == counts
        )
        review_evidence(db, evidence, decision="accept", actor="fixture")
        review_evidence(db, evidence, decision="revoke", actor="fixture")
        assert inspect(db, LEARNER, evidence, guard)["status"] == "unknown"
        db.close()

    board = chess.Board("1k3b2/8/8/R4n2/3B4/8/8/1K6 w - - 0 1")
    non_guard = assess(
        board,
        board.parse_uci("d4c5"),
        chess.D4,
        time.monotonic,
        time.monotonic(),
        5,
        [0],
        lambda: None,
        lambda: None,
    )
    assert non_guard["status"] == "supported" and non_guard["guard_witness"] is None
    assert non_guard["captures"][0]["recapture"] == "a5c5"

    for fen, move in (
        ("k7/8/8/5n2/2RB4/8/7K/8 w - - 0 1", "c4c3"),
        ("k7/8/8/5n2/3B4/8/4K3/2R5 w - - 0 1", "c1c4"),
    ):
        board = chess.Board(fen)
        assert (
            assess(
                board,
                board.parse_uci(move),
                chess.D4,
                time.monotonic,
                time.monotonic(),
                5,
                [0],
                lambda: None,
                lambda: None,
            )["status"]
            == "unknown"
        )


def _guard_style_report_workflow(tmp_path, monkeypatch):
    import chess.engine
    import chess.pgn

    from chess_coach.db import Database
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.style_report import style_report
    from chess_coach.web import create_app
    from tests.test_deep_execution import options

    cases = (
        (
            "white",
            ["e2e4", "b8c6", "f1c4", "c6a5"],
            "c4d3",
            "d1e2",
            ["c4d3", "g8f6", "d1e2", "e7e6"],
            ["d1e2", "a5c4", "e2c4", "g8f6"],
        ),
        (
            "black",
            ["a2a3", "e7e5", "b1c3", "f8c5", "c3a4"],
            "c5d6",
            "d8e7",
            ["c5d6", "g1f3", "d8e7", "d2d3"],
            ["d8e7", "a4c5", "e7c5", "g1f3"],
        ),
    )
    for color, prefix, played, guard, played_pv, guard_pv in cases:
        board = chess.Board()
        game = chess.pgn.Game()
        game.headers["White"] = LEARNER if color == "white" else "fixture_opponent"
        game.headers["Black"] = LEARNER if color == "black" else "fixture_opponent"
        game.headers["UTCDate"] = "2026.01.01"
        game.headers["UTCTime"] = "12:00:00"
        game.headers["Result"] = "*"
        node = game
        moves = [*prefix, played]
        for text in moves:
            move = board.parse_uci(text)
            node = node.add_variation(move)
            board.push(move)
        target_ply = len(prefix)
        target_fen = chess.Board()
        for text in prefix:
            target_fen.push_uci(text)

        target_text = target_fen.fen()

        class FixtureEngine:
            def __init__(
                self,
                target=target_text,
                played=played,
                guard=guard,
                moves=tuple(moves),
                played_pv=tuple(played_pv),
                guard_pv=tuple(guard_pv),
            ):
                self.id = {"name": "Synthetic"}
                self.options = {}
                self.target, self.played, self.guard = target, played, guard
                self.moves, self.played_pv, self.guard_pv = moves, played_pv, guard_pv

            def configure(self, _settings):
                pass

            def analyse(self, position, limit, multipv, root_moves=None):
                if position.fen() == self.target:
                    roots = (
                        root_moves
                        or [chess.Move.from_uci(self.played), chess.Move.from_uci(self.guard)][
                            :multipv
                        ]
                    )
                else:
                    actual = position.parse_uci(self.moves[len(position.move_stack)])
                    roots = (
                        root_moves
                        or [actual, *(move for move in position.legal_moves if move != actual)][
                            :multipv
                        ]
                    )
                result = []
                for root in roots:
                    if position.fen() == self.target and root.uci() in {self.played, self.guard}:
                        pv = self.played_pv if root.uci() == self.played else self.guard_pv
                        line = [chess.Move.from_uci(text) for text in pv]
                    else:
                        line = [root]
                        cursor = position.copy()
                        cursor.push(root)
                        for _ in range(3):
                            reply = next(iter(cursor.legal_moves))
                            line.append(reply)
                            cursor.push(reply)
                    result.append(
                        {
                            "score": chess.engine.PovScore(chess.engine.Cp(0), position.turn),
                            "pv": line,
                            "nodes": 100,
                            "depth": 5,
                            "time": 0.01,
                        }
                    )
                return result

            def quit(self):
                pass

        path = tmp_path / ("guard-style-" + color + ".sqlite")
        db = Database(path)
        db.initialize()
        ingest_pgn(db, str(game))
        monkeypatch.setattr(
            chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: FixtureEngine()
        )
        config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
        assert (
            run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))[
                "status"
            ]
            == "complete"
        )
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=1 AND ply=?", (target_ply + 1,)
        ).fetchone()[0]
        selected = select_deep(db, [1], learner=LEARNER, per_game=4, total=4)
        selection = selected["games"][0]["selection_id"]
        assert run_deep(db, selection, learner=LEARNER, options=options(max_jobs=4, multipv=2))[
            "status"
        ] in {"complete", "partial"}
        evidence = process_decision(db, position, LEARNER)["evidence_ids"][0]
        monkeypatch.setattr(
            chess.engine.SimpleEngine,
            "popen_uci",
            lambda *_args, **_kwargs: pytest.fail("report must not run an engine"),
        )
        before = db.connection.total_changes
        report = style_report(db, LEARNER)
        assert db.connection.total_changes == before
        item = next(value for value in report["observations"] if value["position_id"] == position)
        assert item["choices"]["protect_guard"] == "moved_target"
        pair = next(
            value for value in item["pairs"] if value["alternative_line"]["root_move"] == guard
        )
        assert pair["played"]["protection"]["exchange"]["status"] == "supported"
        assert pair["alternative"]["protection"]["exchange"]["guard_witness"]
        assert pair["guard_comparison"] == "moved_target"
        assert report["dimensions"]["protect_guard"]["direction"] is None
        assert report["dimensions"]["protect_guard"]["trend"] is None
        assert report["protection_coverage"]["used"] <= 20
        from chess_coach import style_report as style_report_module

        with monkeypatch.context() as limited:
            limited.setattr(
                style_report_module,
                "PROTECTION_WORK_LIMIT",
                report["protection_coverage"]["used"] - 1,
            )
            partial = style_report(db, LEARNER)
        assert partial["protection_coverage"]["exchange_unknown"] > 0
        assert not any(
            value["choices"].get("protect_guard") == "moved_target"
            for value in partial["observations"]
        )
        app = create_app(
            db_path=path,
            subject=LEARNER,
            actor="fixture",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        page = app.test_client().get(
            "/style-choices",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert page.status_code == 200 and b"adds a defender" in page.data
        section = page.data.split(b"<h3>Adding a defender</h3>", 1)[1].split(b"</section>", 1)[0]
        assert b"These are descriptive counts, not a preference estimate." in section
        assert b"no direction estimated" in section
        assert b"No trend direction is estimated" in section
        assert b"Sample direction:" not in section and b"direction None" not in section
        assert b"Other quiet moves, compensation and later threats remain unknown" in page.data
        assert f"/evidence/{evidence}".encode() in page.data
        review_evidence(db, evidence, decision="accept", actor="fixture")
        review_evidence(db, evidence, decision="revoke", actor="fixture")
        stale = style_report(db, LEARNER)
        assert not any(
            value["choices"].get("protect_guard") == "moved_target"
            for value in stale["observations"]
        )
        db.close()


def test_successful_protection_transfer_workflow(tmp_path, monkeypatch, capsys):
    from chess_coach.cli import main
    from chess_coach.web import create_app

    _guard_inspection_workflow(tmp_path, monkeypatch, capsys)
    _guard_style_report_workflow(tmp_path, monkeypatch)

    # A threatened piece may itself capture the attacker.
    fen = "4k3/8/8/2b5/3Q4/8/P7/7K w - - 0 1"
    features = protection_features(fen, ["d4c5"])
    assert features["mechanism"] == "move_threatened_piece"
    assert plausible(fen, ["d4c5"], features)

    for color in ("white", "black"):
        path = tmp_path / (color + ".sqlite")
        db = make_protection_game(path, monkeypatch, played="d4d5", color=color)
        evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
        from chess_coach import objective_protection_source, related_protection_source

        with monkeypatch.context() as patch:
            current = Mock(wraps=objective_protection_source.current)
            patch.setattr(objective_protection_source, "current", current)
            related_protection_source.source_for_evidence(db, LEARNER, evidence)
            assert current.call_count == 2
            view, review = current(
                db, evidence, LEARNER, kind="material_protection", operation="prevent"
            )
            current.side_effect = [(view, review), (dict(view, outcome="changed"), review)]
            with pytest.raises(ValueError, match="source changed"):
                related_protection_source.source_for_evidence(db, LEARNER, evidence)
        from chess_coach.protection_game_review import binding as game_review

        protection_marker, blocked = game_review(db, 1, LEARNER)
        assert not blocked
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
        )
        db.connection.commit()
        assert game_review(db, 1, LEARNER)[1] == {1}
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value-1 WHERE position_id=1"
        )
        db.connection.commit()
        assert game_review(db, 1, LEARNER) == (protection_marker, set())
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
        )
        corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
        setup = chess.Board("4k3/7p/8/2b5/3R4/8/P7/7K b - - 0 1")
        from chess_coach.related_capture_familiar import _initial_prompt
        from chess_coach.related_capture_position import prompt_key

        assert _initial_prompt('[Event "standard"]\n\n*') == prompt_key(chess.STARTING_FEN)
        assert _initial_prompt(f'[FEN "{setup.fen()}"]\n\n*') == prompt_key(setup.fen())
        moves = ["h7h6", "d4d5"]
        if color == "black":
            setup = setup.mirror()
            moves = [
                chess.Move(
                    chess.square_mirror(m.from_square), chess.square_mirror(m.to_square)
                ).uci()
                for m in map(chess.Move.from_uci, moves)
            ]
        # The real match comes after the former 100-row per-band limit.
        records = [(f"a{i:03}", "bad", "bad") for i in range(120)]
        other = "a2a3" if color == "white" else "a7a6"
        pawn_from = "a2" if color == "white" else "a7"
        alternatives = []
        for file in ("b", "c", "e", "g", "f", "h"):
            alternate = setup.copy()
            pawn = alternate.remove_piece_at(chess.parse_square(pawn_from))
            alternate.set_piece_at(chess.parse_square(file + pawn_from[1]), pawn)
            alternatives.append(alternate)
        extra = setup.copy()
        king_from = chess.H1 if color == "white" else chess.H8
        king_to = chess.G2 if color == "white" else chess.G7
        extra.set_piece_at(king_to, extra.remove_piece_at(king_from))
        nonzero = "e8f8" if color == "white" else "e1f1"
        records += [
            ("w-unknown-history", setup.fen(), f"{nonzero} {moves[1]}"),
            ("x-wrong-role", setup.fen(), f"{moves[0]} {other}"),
            ("y-malformed", setup.fen(), f"{moves[0]} {moves[1]} invalid invalid"),
            ("z-match", setup.fen(), " ".join(moves)),
            ("z-second", alternatives[0].fen(), " ".join(moves)),
            ("z-third", alternatives[1].fen(), " ".join(moves)),
            ("z-fourth", alternatives[2].fen(), " ".join(moves)),
            ("z-fifth", alternatives[3].fen(), " ".join(moves)),
            ("z-sixth", extra.fen(), " ".join(moves)),
            ("z-seventh", alternatives[5].fen(), " ".join(moves)),
        ]
        db.connection.executemany(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,? ,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            [(key, corpus, board, line) for key, board, line in records],
        )
        db.connection.executemany(
            "INSERT INTO puzzle_themes VALUES(?,?,'defensiveMove',1200)",
            [(corpus, key) for key, _, _ in records],
        )
        db.connection.execute("UPDATE puzzles SET rating=1400 WHERE puzzle_id='z-second'")
        db.connection.execute("UPDATE puzzle_themes SET rating=1400 WHERE puzzle_id='z-second'")
        db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
        db.connection.commit()
        result = preview(db, LEARNER, evidence, "test")
        assert result["source_outcome"] == "success"
        assert len(result["items"]) == 4 and result["scanned"] == 130
        assert result["protection_scan"]["checked"] == 8
        assert all(item["assessment_available"] for item in result["items"])
        from chess_coach.related_protection_assessment import certificate

        with pytest.raises(ValueError):
            certificate(
                db, "test", "w-unknown-history", result["items"][0]["objective_target"], [moves[1]]
            )

        import time

        from chess_coach.objective_protection_before import probe as protection_probe
        from chess_coach.objective_protection_judge import judge as protection_judge
        from chess_coach.related_capture_assessment import setup as assessment_setup

        candidate_board, _, _ = assessment_setup(db, "test", "z-match")
        target = next(iter(protection_probe(candidate_board)["targets"]))
        wrong = "d4b4" if color == "white" else "d5b5"
        uncertain = "a2a3" if color == "white" else "a7a6"
        for move, status in ((wrong, "incorrect"), (uncertain, "unresolved")):
            verdict = protection_judge(
                candidate_board,
                candidate_board.parse_uci(move),
                target,
                time.monotonic,
                time.monotonic(),
                5.0,
                {},
            )
            assert verdict["status"] == status
        from chess_coach.protection_game_proof import classify as protection_game

        for move, expected in (
            (moves[1], "protected"),
            (wrong, "missed"),
            (uncertain, "opportunity_unresolved"),
        ):
            assert (
                protection_game(candidate_board, move, time.monotonic() + 5, time.monotonic)[0]
                == expected
            )
        assert protection_game(chess.Board(), "e2e4", time.monotonic() + 5, time.monotonic) == (
            "no_opportunity",
            None,
        )
        assert protection_game(candidate_board, moves[1], 0, time.monotonic) == (
            "unknown",
            "deadline",
        )

        # Once a contrast is proved, an expired played check remains an opportunity.
        from chess_coach import protection_game_before as before_game
        from chess_coach import protection_game_proof as game_proof

        with monkeypatch.context() as patch:
            now = [0]

            def clock(now=now):
                return now[0]

            patch.setattr(
                game_proof, "before", lambda *_, target=target: ({"targets": [target]}, None)
            )
            contrast = game_proof._contrast
            patch.setattr(game_proof, "_contrast", lambda *_: True)

            def expired(*_args, now=now):
                now[0] = 1
                return "correct"

            patch.setattr(game_proof, "status", expired)
            assert game_proof.classify(candidate_board, moves[1], 1, clock) == (
                "opportunity_unresolved",
                "deadline",
            )
            patch.setattr(game_proof, "_contrast", contrast)
            now[0] = 0
            assert game_proof.classify(candidate_board, moves[1], 1, clock) == (
                "unknown",
                "deadline",
            )
            patch.setattr(game_proof, "_contrast", lambda *_: False)
            assert game_proof.classify(candidate_board, moves[1], 1, clock) == (
                "unknown",
                "contrast_unresolved",
            )
            patch.setattr(before_game, "judge", lambda *_: pytest.fail("expired judge called"))
            assert (
                before_game.status(candidate_board, chess.Move.from_uci(moves[1]), target, 1, clock)
                == "unresolved"
            )

        from chess_coach.related_protection_assessment import valid as certificate_valid

        candidate_board, _, fingerprint = assessment_setup(db, "test", "z-match")
        certificate_value = certificate(
            db, "test", "z-match", chess.square_name(target), [moves[1]]
        )
        assert certificate_valid(
            candidate_board, fingerprint, certificate_value, chess.square_name(target), [moves[1]]
        )
        assert not certificate_valid(
            candidate_board, fingerprint, certificate_value, chess.square_name(target), [wrong]
        )
        with pytest.raises(ValueError):
            certificate(db, "test", "z-match", chess.square_name(target), [wrong])
        assert json.dumps(moves[1]) not in json.dumps(result)
        reference = next(item["reference"] for item in result["items"] if item["rating"] == 1200)
        with pytest.raises(ValueError):
            preview(db, "other", evidence, "test")

        import chess_coach.related_protection_start as protection_start

        original_admit = protection_start.admit

        def concurrent_commit(*args, db=db, original_admit=original_admit, path=path):
            assert not db.connection.in_transaction
            selected = original_admit(*args)
            other_db = sqlite3.connect(path)
            other_db.execute("PRAGMA user_version = 1")
            other_db.close()
            return selected

        with monkeypatch.context() as patch:
            patch.setattr(protection_start, "admit", concurrent_commit)
            with pytest.raises(ValueError, match="changed"):
                start_related(
                    db,
                    attempt_id="race",
                    subject=LEARNER,
                    evidence_id=evidence,
                    corpus_version="test",
                    reference=reference,
                )
        assert (
            db.connection.execute(
                "SELECT COUNT(*) FROM unified_sessions WHERE attempt_id='race'"
            ).fetchone()[0]
            == 0
        )
        db.close()

        if color == "white":
            # Keyset continuation reaches a late match even after a newer import.
            import chess_coach.protection_finder_scan as scan
            import chess_coach.protection_finder_window as window
            from chess_coach.protection_finder_cursor import state_for
            from chess_coach.protection_finder_scan import Finder

            records = list(range(100, 40, -1))
            visited = []

            class Checks:
                def __init__(self, visited=visited):
                    self.checked = 0
                    self.result = {"items": []}
                    self.visited = visited

                def check(self):
                    pass

                def source(self, identity):
                    self.visited.append(identity)
                    if identity == 56:
                        self.result = {"items": [identity]}

            with monkeypatch.context() as patch:
                patch.setattr(
                    window,
                    "rows",
                    lambda db, who, phase, before, lower, records=records: [
                        {"id": identity} for identity in records if lower <= identity < before
                    ][:32],
                )
                patch.setattr(scan, "preferred", lambda page, row, phase: True)
                signer, state = state_for(b"secret", LEARNER, "test", None)
                state[1] = 1
                for _ in range(3):
                    checks = Checks()
                    search = Finder(None, LEARNER, state, checks)
                    search.run()
                    if checks.result["items"]:
                        break
                    records.insert(0, 101)
                    token = signer.dumps(search.state)
                    _, state = state_for(b"secret", LEARNER, "test", token)
                assert checks.result["items"] == [56]
                assert visited == list(range(100, 55, -1))

            # A resumed failure keeps the companion already checked in this window.
            from chess_coach.material_contract import SCOPE, VERSION
            from chess_coach.material_policy import MAPPER

            markers = [
                {
                    "id": identity,
                    "outcome": "failure",
                    "mapper_version": VERSION,
                    "game_id": 1 if identity == 100 else 2,
                    "producer": MAPPER,
                    "run_version": VERSION,
                    "scope_key": SCOPE,
                    "status": "active",
                    "review": None,
                }
                for identity in range(100, 96, -1)
            ]
            checked = []

            class SourceChecks:
                def __init__(self, checked=checked):
                    self.checked = 0
                    self.result = {"items": []}
                    self.visited = checked

                def check(self):
                    pass

                def source(self, identity):
                    self.checked += 1
                    self.visited.append(identity)
                    if identity == 97:
                        self.result = {"items": [identity]}

            with monkeypatch.context() as patch:
                patch.setattr(
                    window,
                    "rows",
                    lambda db, who, phase, before, lower, markers=markers: (
                        [row for row in markers if lower <= row["id"] < before]
                        if phase == 0
                        else []
                    ),
                )
                signer, state = state_for(b"secret", LEARNER, "test", None)
                first = Finder(None, LEARNER, state, SourceChecks())
                first.run()
                assert checked == [100, 99, 98]
                _, resumed = state_for(b"secret", LEARNER, "test", signer.dumps(first.state))
                second = Finder(None, LEARNER, resumed, SourceChecks())
                second.run()
                assert checked == [100, 99, 98, 97]
                assert second.checks.result["items"] == [97]

                # A timed-out source is skipped, but remains recurrence context.
                class Timed(SourceChecks):
                    def source(self, identity):
                        self.visited.append(identity)
                        raise TimeoutError

                checked.clear()
                _, state = state_for(b"secret", LEARNER, "test", None)
                timed = Finder(None, LEARNER, state, Timed())
                with pytest.raises(TimeoutError):
                    timed.run()
                _, resumed = state_for(b"secret", LEARNER, "test", signer.dumps(timed.state))
                after_timeout = Finder(None, LEARNER, resumed, SourceChecks())
                after_timeout.run()
                assert checked == [100, 99, 98, 97]
                assert after_timeout.checks.result["items"] == [97]

            # The deadline applies while validating old puzzle-session lines too.
            from types import SimpleNamespace

            from chess_coach.related_capture_familiar import _legacy_sessions

            legacy = SimpleNamespace(
                connection=SimpleNamespace(
                    execute=lambda *args: SimpleNamespace(fetchall=lambda: [{}])
                )
            )

            def expired():
                raise TimeoutError

            with pytest.raises(TimeoutError):
                _legacy_sessions(legacy, check=expired)

            # One familiarity snapshot serves every strict source check in a request.
            import chess_coach.protection_finder_work as work

            loads = []
            selections = []
            familiar = (set(), set(), lambda key: False)
            with monkeypatch.context() as patch:
                patch.setattr(work, "source_for_evidence", lambda *args: None)
                patch.setattr(
                    work,
                    "familiarity",
                    lambda *args, loads=loads, familiar=familiar, **kwargs: (
                        loads.append(1) or familiar
                    ),
                )
                patch.setattr(
                    work,
                    "selection",
                    lambda *args, selections=selections, **kwargs: (
                        selections.append(kwargs["familiar_data"]) or None
                    ),
                )
                checks = work.SourceChecks(None, LEARNER, "test", float("inf"))
                checks.source(1)
                checks.source(2)
            assert loads == [1] and selections == [familiar, familiar]

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "chess-coach",
                "--db",
                str(path),
                "related-protections",
                "--subject",
                LEARNER,
                "--evidence",
                str(evidence),
                "--corpus",
                "test",
            ],
        )
        main()
        assert reference in [
            item["reference"] for item in json.loads(capsys.readouterr().out)["items"]
        ]

        app = create_app(
            db_path=path,
            subject=LEARNER,
            actor="fixture",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        client = app.test_client()
        headers = {"Tailscale-User-Login": "fixture"}
        empty_progress = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"No certified unfamiliar protection assessments" in empty_progress.data
        assert (
            client.get(
                f"/evidence/{2**63}/related-protections",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 400
        )
        source = client.get(
            f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
        )
        assert b"Find related protection practice" in source.data
        # The opt-in finder uses the same proof and creates no attempt on GET.
        observer = sqlite3.connect(path)
        before = observer.execute("PRAGMA data_version").fetchone()[0]
        finder = client.get(
            "/plan/protection/finder", base_url="https://coach.invalid", headers=headers
        )
        assert observer.execute("PRAGMA data_version").fetchone()[0] == before
        observer.close()
        assert finder.status_code == 200
        assert b"successful defense for rehearsal" in finder.data
        assert b"Start this example" in finder.data
        assert b"Check my first move" in finder.data
        assert any(item["reference"].encode() in finder.data for item in result["items"])
        move = re.escape(moves[1].encode())
        move_token = rb"(?<![A-Za-z0-9_-])" + move + rb"(?![A-Za-z0-9_-])"
        assert not re.search(move_token, finder.data)
        assert re.search(move_token, b"<p>" + moves[1].encode() + b"</p>")
        assert not re.search(move_token, b'csrf="opaque' + moves[1].encode() + b'opaque"')
        assert (
            client.get(
                "/plan/protection/finder?cursor=tampered",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 400
        )

        page = client.get(
            f"/evidence/{evidence}/related-protections",
            base_url="https://coach.invalid",
            headers=headers,
        )
        assert b"successful defense rehearsal" in page.data
        assert b"Check my first move" in page.data
        assert f"You play {color}".encode() in page.data
        assert not re.search(move_token, page.data)
        with client.session_transaction(base_url="https://coach.invalid") as session:
            csrf = session["csrf"]
        url = f"/evidence/{evidence}/related-protections/start"
        data = {"csrf": csrf, "reference": reference}
        assert (
            client.post(
                url, base_url="https://coach.invalid", headers=headers, data=data
            ).status_code
            == 403
        )
        response = client.post(
            url,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data=data,
        )
        assert response.status_code == 303
        played = client.get(response.location, base_url="https://coach.invalid", headers=headers)
        assert played.status_code == 200 and b"supplied line is an example" in played.data
        with client.session_transaction(base_url="https://coach.invalid") as session:
            attempt = session["unified_attempt"]

        from chess_coach.db import Database

        db = Database(path)
        # Isolate the deviation to preserve the existing assessment selection.
        copied_path = tmp_path / (color + "-rehearsal.sqlite")
        copied = Database(copied_path)
        db.connection.backup(copied.connection)
        board = chess.Board(show(copied, attempt, LEARNER)["fen"])
        lines = json.loads(
            copied.connection.execute(
                "SELECT lines_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
        )
        first_moves = {line[0] for line in lines if line}
        alternative = next(
            move.uci() for move in board.legal_moves if move.uci() not in first_moves
        )
        unlisted = submit(copied, attempt, LEARNER, event_id="unlisted", move=alternative)
        assert unlisted["status"] == unlisted["feedback"] == "ungraded"
        assert "source_key" not in show(copied, attempt, LEARNER)
        assert (
            copied.connection.execute(
                "SELECT COUNT(*) FROM objective_requests WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
            == 0
        )
        copied.close()
        copied_app = create_app(
            db_path=copied_path,
            subject=LEARNER,
            actor="fixture",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        related_page = copied_app.test_client().get(
            response.location, base_url="https://coach.invalid", headers=headers
        )
        assert b"no verification was queued" in related_page.data
        assert b"Restart this exercise" not in related_page.data
        assert b'name="key"' not in related_page.data
        assert (
            submit(db, attempt, LEARNER, event_id="move", move=moves[1])["status"]
            == "line_completed"
        )

        # A different still-unfamiliar candidate supports an independently checked first move.
        fresh = preview(db, LEARNER, evidence, "test")
        assert len(fresh["items"]) == 4 and fresh["items"][0]["assessment_available"]
        fresh_item = next(item for item in fresh["items"] if item["rating"] == 1200)
        assessment = client.post(
            url,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": csrf, "reference": fresh_item["reference"], "assessment": "1"},
        )
        assert assessment.status_code == 303
        with client.session_transaction(base_url="https://coach.invalid") as session:
            assessment_attempt = session["unified_attempt"]
        from chess_coach.objective_worker import process as verify
        from chess_coach.unified_session_events import hint

        if color == "black":
            hint(db, assessment_attempt, LEARNER, event_id="hint")
        answer = submit(db, assessment_attempt, LEARNER, event_id="answer", move=moves[1])
        assert answer["status"] == "needs_verification"
        assert verify(db, LEARNER)["processed"] == 1
        checked = show(db, assessment_attempt, LEARNER)
        assert checked["verification"]["status"] == "correct"
        assert checked["verification"]["assistance"] == (
            "unassisted" if color == "white" else "hinted"
        )
        assert checked["protection_assessment"] and checked["protection_target"]

        from chess_coach.protection_plan_history import report as assessment_history

        history = assessment_history(db, LEARNER, "test", evidence)
        from chess_coach.protection_progress import report as protection_progress

        progress_before = db.connection.total_changes
        progress_history = protection_progress(db, LEARNER, "test")
        assert db.connection.total_changes == progress_before
        progress_entry = next(
            entry for entry in progress_history["items"] if entry["attempt"] == assessment_attempt
        )
        assert progress_entry["status"] == ("correct" if color == "white" else "unavailable")
        if color == "white":
            answered = db.connection.execute(
                "SELECT e.created_at FROM objective_requests q JOIN unified_session_events e "
                "ON e.attempt_id=q.attempt_id AND e.event_id=q.event_id WHERE q.attempt_id=?",
                (assessment_attempt,),
            ).fetchone()
            assert progress_entry["answered_at"] == answered["created_at"]
        assert client.get("/plan/protection/progress").status_code == 403
        progress_page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert progress_page.status_code == 200 and b"Matched samples" in progress_page.data
        if color == "white":
            assert history["status"] == "correct" and history["evidence_id"] == evidence
            separate = assessment_history(db, LEARNER, "test", evidence + 1)
            assert separate == history
            page = client.get(
                f"/evidence/{evidence}/related-protections?followup={assessment_attempt}",
                base_url="https://coach.invalid",
                headers=headers,
            )
            assert page.status_code == 200 and b"200-point content-rating band" in page.data
            from chess_coach.protection_difficulty import eligible as harder_eligible

            with pytest.raises(ValueError):
                harder_eligible(db, LEARNER, "test", evidence, assessment_attempt)
            next_item = next(
                item
                for item in preview(db, LEARNER, evidence, "test")["items"]
                if item["rating"] == 1200
            )
            start_related(
                db,
                attempt_id="second-correct",
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=next_item["reference"],
                assessment=True,
                followup=assessment_attempt,
            )
            submit(db, "second-correct", LEARNER, event_id="answer", move=moves[1])
            assert verify(db, LEARNER)["processed"] == 1
            assessment_attempt = "second-correct"
            history = assessment_history(db, LEARNER, "test", evidence)
            assert harder_eligible(db, LEARNER, "test", evidence, assessment_attempt)[0][3] == 7
            from chess_coach.related_protection import selection as protection_selection

            scoped = protection_selection(db, LEARNER, evidence, "test", difficulty=(7, color))
            assert scoped[2]["scanned"] == scoped[2]["protection_scan"]["checked"] == 1
            import chess_coach.protection_difficulty_filter as difficulty_filter

            with monkeypatch.context() as patch:
                patch.setattr(
                    difficulty_filter, "_prompt", lambda *_: pytest.fail("wrong side replayed")
                )
                wrong_side = "black" if color == "white" else "white"
                assert not difficulty_filter.accepts(
                    {"type": "corpus", "rating": 1400, "fen": setup.fen()},
                    None,
                    None,
                    (7, wrong_side),
                    {},
                )
            harder = client.get(
                f"/evidence/{evidence}/related-protections?followup={assessment_attempt}&harder=1",
                base_url="https://coach.invalid",
                headers=headers,
            )
            assert harder.status_code == 200 and b"1400" in harder.data
            harder_match = re.search(rb'name="reference" value="([^"]+)"', harder.data)
            assert harder_match is not None
            harder_ref = harder_match.group(1).decode()
            started_harder = client.post(
                url,
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={
                    "csrf": csrf,
                    "reference": harder_ref,
                    "assessment": "1",
                    "followup": assessment_attempt,
                    "harder": "1",
                },
            )
            assert started_harder.status_code == 303
            with pytest.raises(ValueError):
                harder_eligible(db, LEARNER, "test", evidence, assessment_attempt)
            import chess_coach.web_protection_plan as plan_web

            source = {
                "evidence_id": evidence + 1,
                "markers": 2,
                "games": 2,
                "review_status": "provisional",
                "color": color,
                "version": "fixture",
                "key": "1",
            }
            group = {
                "source": source,
                "scanned": 2,
                "groups": 1,
                "checked": 1,
                "unavailable": 0,
                "limited": False,
                "partial": False,
            }
            version = db.connection.execute("PRAGMA data_version").fetchone()[0]
            with monkeypatch.context() as patch:
                patch.setattr(plan_web, "report", lambda *_, group=group: group)
                patch.setattr(
                    "chess_coach.related_protection.selection",
                    lambda *_args, **_kwargs: pytest.fail("plan searched the corpus"),
                )
                patch.setattr(
                    "chess_coach.related_fork_assessment_finder.selection",
                    lambda *_args, **_kwargs: pytest.fail("plan searched the corpus"),
                )
                view = client.get(
                    "/plan/protection", base_url="https://coach.invalid", headers=headers
                )
                assert view.status_code == 200
                assert b"assessment source is separate" in view.data
                assert f"/evidence/{evidence}/related-protections?followup=".encode() in view.data
                assert b"general finder" in view.data
                assert (
                    b"<title>Piece-protection rehearsal \xe2\x80\x94 Chess coach</title>"
                    in view.data
                )
                assert view.data.count(b"Find a comparable unfamiliar protection assessment") == 1
                patch.setattr(plan_web, "admissible", lambda *_: None)
                patch.setattr(plan_web, "fork_recommendation", lambda *_: None)
                focus = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"<title>Next practice focus \xe2\x80\x94 Chess coach</title>" in focus.data
                assert focus.data.count(b"Find a comparable unfamiliar protection assessment") == 1
                due = {
                    "objective": "Due review",
                    "kind": "due",
                    "reason": "",
                    "due": None,
                    "corpus_version": "test",
                    "puzzle_id": "due",
                }
                new = {**due, "objective": "New puzzle", "kind": "new", "puzzle_id": "new"}
                plan = {
                    "items": [due, new],
                    "scan": {"due_incomplete": False},
                    "evidence": {"state": "fixture"},
                    "corpus_status": "fixture",
                    "diagnostic": None,
                    "next_cursor": None,
                }
                patch.setattr("chess_coach.web_views.daily_plan", lambda *_, plan=plan, **_k: plan)
                patch.setattr("chess_coach.plan_page.promotion_recommendation", lambda *_: None)
                daily = client.get("/plan", base_url="https://coach.invalid", headers=headers)
                assert (
                    daily.data.index(b"Due review")
                    < daily.data.index(b"Next focus: protect a piece")
                    < daily.data.index(b"New puzzle")
                )
                assert b"Replay the prepared defensive line" in daily.data
                assert b"prepared replay is provisional" in daily.data
                assert b"independent candidate games" in daily.data
                assert f'name="key" value="{source["key"]}"'.encode() in daily.data

                def plan_data(path="/plan", client=client, headers=headers):
                    return client.get(path, base_url="https://coach.invalid", headers=headers).data

                ready_promotion = {
                    "status": "ready",
                    "version": "fixture",
                    "key": "white",
                    "color": "white",
                    "objective": "promote_now",
                }
                with patch.context() as promotion_check:
                    promotion_check.setattr(
                        "chess_coach.plan_page.promotion_recommendation",
                        lambda *_, ready_promotion=ready_promotion: ready_promotion,
                    )
                    prioritized = plan_data()
                    assert (
                        prioritized.index(b"Due review")
                        < prioritized.index(b"Next focus: promotion practice")
                        < prioritized.index(b"Available recurring practice: protect a piece")
                        < prioritized.index(b"New puzzle")
                    )
                    assert prioritized.count(b"Start promotion practice") == 1
                    explanation = prioritized.split(b"Next focus: promotion practice", 1)[1].split(
                        b"</section>", 1
                    )[0]
                    assert f'href="/evidence/{evidence}"'.encode() in explanation
                    assert f'href="/evidence/{source["evidence_id"]}"'.encode() not in explanation
                    for status in ("pending", "unknown", "incorrect"):
                        with promotion_check.context() as unresolved:
                            unresolved.setattr(
                                plan_web,
                                "protection_history",
                                lambda *_, status=status: {"status": status, "target": "d4"},
                            )
                            assert b"Next focus: promotion practice" not in plan_data()
                    plan["scan"]["due_incomplete"] = True
                    assert b"Next focus: promotion practice" not in plan_data()
                    plan["scan"]["due_incomplete"] = False
                    assert b"Next focus: promotion practice" not in plan_data("/plan?cursor=next")
                    with promotion_check.context() as unavailable:
                        unavailable.setattr(
                            "chess_coach.plan_page.promotion_recommendation",
                            lambda *_: {"status": "complete"},
                        )
                        assert b"Next focus: promotion practice" not in plan_data()

                assert (
                    f"/evidence/{source['evidence_id']}/related-protections".encode() in daily.data
                )
                assert f'href="/evidence/{evidence}"'.encode() in daily.data
                assert b"separate from this selected rehearsal" in daily.data
                assert b"Matched protection assessment progress" in daily.data
                assert b"Protection choices in your games" in daily.data
                assert b"Find a harder unfamiliar protection assessment" not in daily.data
                source_url = f"/evidence/{source['evidence_id']}/related-protections"
                assert (source_url + "?from_plan=1").encode() in daily.data
                with patch.context() as unavailable:

                    def unknown_history(*_args, **_kwargs):
                        raise ValueError("protection history unavailable")

                    unavailable.setattr(
                        "chess_coach.web_related_protection.preview", unknown_history
                    )
                    check = client.get(
                        source_url + "?from_plan=1",
                        base_url="https://coach.invalid",
                        headers=headers,
                    )
                    assert check.status_code == 200 and b"This source is unavailable" in check.data
                    assert b'href="/plan/protection/finder"' in check.data
                    assert (
                        client.get(
                            source_url, base_url="https://coach.invalid", headers=headers
                        ).status_code
                        == 400
                    )
                    assert (
                        client.get(
                            source_url + "?from_plan=1&cursor=bad",
                            base_url="https://coach.invalid",
                            headers=headers,
                        ).status_code
                        == 400
                    )
                plan["scan"]["due_incomplete"] = True
                assert b"Next focus: protect a piece" not in plan_data()
                plan["scan"]["due_incomplete"] = False
                assert b"Next focus: protect a piece" not in plan_data("/plan?cursor=next")

                capture = {
                    "source": {
                        "games": 1,
                        "position_id": 1,
                        "evidence_id": evidence,
                        "reviewed": False,
                        "version": "fixture",
                        "key": "fixture",
                    },
                    "history": {"status": "none"},
                    "limited": False,
                    "scanned": 2,
                }
                fork = {
                    "source": {"evidence_id": evidence, "version": "fixture", "key": "fixture"},
                    "games": 2,
                    "assessment": {"status": "unknown"},
                }
                patch.setattr(plan_web, "admissible", lambda *_, capture=capture: capture)
                # A success from a separate owned assessment can add variety while
                # retaining its own source and follow-up.
                rotated = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: find captures" in rotated.data
                assert b"assessment source is separate" in rotated.data
                assert (
                    f"/evidence/{evidence}/related-protections?followup=".encode() in rotated.data
                )
                assert b"verified correct without assistance" in rotated.data
                explanation = rotated.data.split(b"Next focus: find captures", 1)[1].split(
                    b"</p>", 1
                )[0]
                assert f'href="/evidence/{evidence}"'.encode() in explanation
                assert b"separate from the selected protection rehearsal" in explanation
                assert b"selected protection source" in rotated.data

                fork_calls = []

                def optional_fork(*_args, fork=fork, fork_calls=fork_calls):
                    fork_calls.append(True)
                    return fork

                patch.setattr(plan_web, "fork_recommendation", optional_fork)
                fast = client.get("/plan", base_url="https://coach.invalid", headers=headers)
                assert b"Capture practice" in fast.data and not fork_calls
                full = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: find captures" in full.data
                assert b"Optional practice: finding forks" in full.data and fork_calls == [True]
                patch.setattr(plan_web, "fork_recommendation", lambda *_: None)

                # Only an exact-source verified result may advance this card.
                same_result = {
                    **history,
                    "evidence_id": source["evidence_id"],
                    "attempt": assessment_attempt,
                    "harder": True,
                }
                patch.setattr(plan_web, "admissible", lambda *_: None)
                patch.setattr(
                    plan_web, "protection_history", lambda *_, same_result=same_result: same_result
                )
                exact_daily = plan_data()
                exact_path = f"/evidence/{source['evidence_id']}/related-protections?followup={assessment_attempt}"
                assert exact_path.encode() in exact_daily
                assert (exact_path + "&amp;harder=1").encode() in exact_daily
                same_result.update(status="incorrect", target="d4")
                missed_daily = plan_data()
                assert (
                    b"verified miss" in missed_daily
                    and b"threatened piece was on d4" in missed_daily
                )
                assert exact_path.encode() not in missed_daily
                same_result.update(evidence_id=evidence, status="incorrect")
                other_miss = plan_data()
                assert b"separate from this selected rehearsal" in other_miss
                assert b"In that assessment the threatened piece was on d4" in other_miss
                assert (
                    f"/evidence/{source['evidence_id']}/related-protections".encode() in other_miss
                )
                assert b"Find a harder unfamiliar protection assessment" not in other_miss
                same_result["status"] = "unknown"
                unknown_daily = plan_data()
                assert b"No current unassisted assessment result" in unknown_daily
                assert b"Find a harder unfamiliar protection assessment" not in unknown_daily
                assert (
                    f"/evidence/{source['evidence_id']}/related-protections".encode()
                    in unknown_daily
                )
                patch.setattr(plan_web, "admissible", lambda *_, capture=capture: capture)

                same_origin = {**history, "evidence_id": evidence + 1}
                patch.setattr(
                    plan_web, "protection_history", lambda *_, same_origin=same_origin: same_origin
                )
                same_page = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                same_explanation = same_page.data.split(b"Next focus: find captures", 1)[1].split(
                    b"</p>", 1
                )[0]
                assert f'href="/evidence/{evidence + 1}"'.encode() in same_explanation
                assert b"matches the selected protection rehearsal" in same_explanation
                patch.setattr(plan_web, "protection_history", lambda *_, history=history: history)

                patch.setattr(plan_web, "admissible", lambda *_: None)
                patch.setattr(plan_web, "fork_recommendation", lambda *_, fork=fork: fork)
                fork_rotation = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                explanation = fork_rotation.data.split(b"Next focus: finding forks", 1)[1].split(
                    b"</p>", 1
                )[0]
                assert f'href="/evidence/{evidence}"'.encode() in explanation
                assert b"separate from the selected protection rehearsal" in explanation
                daily_fork = client.get("/plan", base_url="https://coach.invalid", headers=headers)
                assert (
                    daily_fork.data.index(b"Due review")
                    < daily_fork.data.index(b"Next focus: finding forks")
                    < daily_fork.data.index(b"New puzzle")
                )
                assert b"Rehearse this fork" in daily_fork.data
                assert f'href="/evidence/{evidence}"'.encode() in daily_fork.data
                patch.setattr(plan_web, "admissible", lambda *_, capture=capture: capture)
                patch.setattr(plan_web, "fork_recommendation", lambda *_: None)

                capture["history"] = {
                    "status": "correct",
                    "assistance": "unassisted",
                    "attempt_id": "capture-result",
                }
                patch.setattr(plan_web, "protection_history", lambda *_: {"status": "unknown"})
                higher_protection = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: protect a piece" in higher_protection.data
                assert b"matching comparison context" in higher_protection.data
                patch.setattr(plan_web, "protection_history", lambda *_, history=history: history)

                capture["source"]["games"] = 3
                capture["history"] = {
                    "status": "correct",
                    "assistance": "unassisted",
                    "attempt_id": "capture-result",
                }
                patch.setattr(plan_web, "fork_recommendation", lambda *_, fork=fork: fork)
                varied = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: finding forks" in varied.data
                assert b"matching comparison context" in varied.data
                assert b"Find a comparable unfamiliar protection assessment" in varied.data
                assert b"Rehearse this fork" in varied.data

                fork["assessment"] = {"status": "correct", "attempt": "fork-result"}
                all_done = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: find captures" in all_done.data
                assert b"matching comparison context" in all_done.data
                assert b"Find a comparable follow-up fork assessment" in all_done.data

                for status, assistance in (
                    ("incorrect", "unassisted"),
                    ("correct", "hinted"),
                    ("pending", "unassisted"),
                    ("unresolved", "unassisted"),
                    ("unavailable", "unassisted"),
                ):
                    capture["history"] = {
                        "status": status,
                        "assistance": assistance,
                        "attempt_id": "sample",
                    }
                    neutral = client.get(
                        "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                    )
                    assert b"Next focus: find captures" in neutral.data
                    if status == "incorrect":
                        assert b"missed the target" in neutral.data

                # With no other source, fork is the primary action and its miss
                # remains a cued rehearsal rather than a success.
                fork["assessment"] = {"status": "incorrect"}
                patch.setattr(plan_web, "admissible", lambda *_: None)
                patch.setattr(plan_web, "report", lambda *_: None)
                only_fork = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"Next focus: finding forks" in only_fork.data
                assert (
                    b"verified miss" in only_fork.data and b"Rehearse this fork" in only_fork.data
                )
                missed_fork = plan_data()
                assert b"verified miss" in missed_fork and b"name both targets" in missed_fork
                assert f"/evidence/{evidence}/related-forks/find-verified".encode() in missed_fork
                assert b"Matched fork assessment progress" in missed_fork
                assert b"Knight forks in your games" in missed_fork
                fork["assessment"] = {"status": "correct", "attempt": "fork-result"}
                correct_fork = plan_data()
                assert b"/plan/forks/next?attempt=fork-result" in correct_fork
                fork["assessment"] = {"status": "unknown"}
                unknown_fork = plan_data()
                assert b"No current unassisted assessment result" in unknown_fork
                assert b"/plan/forks/next?attempt=" not in unknown_fork
                patch.setattr(plan_web, "fork_recommendation", lambda *_: None)
                fallback = client.get("/plan", base_url="https://coach.invalid", headers=headers)
                assert b"Due review" in fallback.data and b"New puzzle" in fallback.data
                assert b"Next focus: finding forks" not in fallback.data
                assert b"Next focus: protect a piece" not in fallback.data
            assert db.connection.execute("PRAGMA data_version").fetchone()[0] == version

            # A write after one family's source check invalidates the entire
            # shared selection in both the daily card and the full focus page.
            counter = [10]

            def changed_generation(*_args, path=path, counter=counter, fork=fork):
                counter[0] += 1
                with sqlite3.connect(path) as writer:
                    writer.execute(f"PRAGMA user_version={counter[0]}")
                return fork

            capture["history"] = {
                "status": "correct",
                "assistance": "unassisted",
                "attempt_id": "capture-result",
            }
            capture["source"]["games"] = 3
            with monkeypatch.context() as patch:
                patch.setattr(plan_web, "admissible", lambda *_, capture=capture: capture)
                patch.setattr(plan_web, "report", lambda *_, group=group: group)
                patch.setattr(plan_web, "protection_history", lambda *_, history=history: history)
                patch.setattr(plan_web, "fork_recommendation", changed_generation)
                patch.setattr("chess_coach.web_views.daily_plan", lambda *_, plan=plan, **_k: plan)
                patch.setattr("chess_coach.plan_page.promotion_recommendation", lambda *_: None)
                changed = client.get("/plan", base_url="https://coach.invalid", headers=headers)
                assert b"Due review" in changed.data and b"New puzzle" in changed.data
                assert b"Capture practice</h3>" not in changed.data
                assert b"Next focus: finding forks" not in changed.data
                full = client.get(
                    "/plan/next-focus", base_url="https://coach.invalid", headers=headers
                )
                assert b"No current recurring practice action" in full.data
                assert b"Optional practice: finding forks" not in full.data

            from chess_coach.db_versioning import CURRENT_VERSION

            db.connection.execute(f"PRAGMA user_version={CURRENT_VERSION}")
            db.connection.commit()

            class Unavailable:
                def execute(self, *_args):
                    raise sqlite3.OperationalError("synthetic unavailable database")

            from types import SimpleNamespace

            assert (
                plan_web.current_focus(SimpleNamespace(connection=Unavailable()), LEARNER, "test")[
                    "selected"
                ]
                is None
            )
        else:
            assert history["status"] == "unknown"

        from chess_coach.puzzle_sessions import start_attempt as start_legacy
        from chess_coach.unified_sessions import start as start_unified

        answered = db.connection.execute(
            "SELECT source_key FROM unified_sessions WHERE attempt_id=?", (assessment_attempt,)
        ).fetchone()["source_key"]
        start_unified(
            db,
            attempt_id="later-replay",
            subject=LEARNER,
            source_type="corpus",
            version="test",
            key=answered,
        )
        assert show(db, assessment_attempt, LEARNER)["verification"]["status"] == "correct"
        if color == "white":
            assert assessment_history(db, LEARNER, "test", evidence)["status"] == "correct"

        for exposure in ("unified", "legacy"):
            available = preview(db, LEARNER, evidence, "test")["items"]
            token = available[0]["reference"]
            active = f"active-{exposure}"
            start_related(
                db,
                attempt_id=active,
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=token,
                assessment=True,
                followup=assessment_attempt if color == "white" and exposure == "unified" else None,
            )
            key = db.connection.execute(
                "SELECT source_key FROM unified_sessions WHERE attempt_id=?", (active,)
            ).fetchone()["source_key"]
            if exposure == "unified":
                start_unified(
                    db,
                    attempt_id="exposed-unified",
                    subject=LEARNER,
                    source_type="corpus",
                    version="test",
                    key=key,
                )
            else:
                start_legacy(db, attempt_id="exposed-legacy", version="test", puzzle_id=key)
            with pytest.raises(ValueError):
                submit(db, active, LEARNER, event_id="answer", move=moves[1])
            assert (
                db.connection.execute(
                    "SELECT COUNT(*) FROM unified_session_events WHERE attempt_id=?", (active,)
                ).fetchone()[0]
                == 0
            )
            assert (
                db.connection.execute(
                    "SELECT COUNT(*) FROM objective_requests WHERE attempt_id=?", (active,)
                ).fetchone()[0]
                == 0
            )

        if color == "white":
            last = preview(db, LEARNER, evidence, "test")["items"][0]
            start_related(
                db,
                attempt_id="verified-miss",
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=last["reference"],
                assessment=True,
            )
            submit(db, "verified-miss", LEARNER, event_id="answer", move=wrong)
            assert verify(db, LEARNER)["processed"] == 1

            # Both exact current assessments contribute, while ineligible attempts stay separate.
            progress_history = protection_progress(db, LEARNER, "test")
            matched_group = next(
                group for group in progress_history["groups"] if group["count"] == 3
            )
            assert matched_group["reason"]
            assert {entry["status"] for entry in progress_history["items"]} == {
                "correct",
                "incorrect",
                "unavailable",
            }
            db.connection.execute(
                """UPDATE unified_sessions SET started_at=(SELECT created_at FROM unified_session_events
                WHERE attempt_id=? AND event_id='answer') WHERE attempt_id=?""",
                ("verified-miss", "verified-miss"),
            )
            db.connection.commit()
            assert assessment_history(db, LEARNER, "test", evidence)["status"] == "incorrect"
            from chess_coach.objective_protection_contract import VERSION as protection_version

            with monkeypatch.context() as patch:
                patch.setattr(plan_web, "report", lambda *_, group=group: group)
                view = client.get(
                    "/plan/protection", base_url="https://coach.invalid", headers=headers
                )
                assert b"Rehearse this assessment source" in view.data
                assert b"check the opponent" in view.data
                assert b'href="/plan/protection/progress"' in view.data
                with app.test_request_context():
                    from flask import url_for

                    start_url = url_for("unified_practice.begin")
                replay = client.post(
                    start_url,
                    base_url="https://coach.invalid",
                    headers=headers | {"Origin": "https://coach.invalid"},
                    data={
                        "csrf": csrf,
                        "source_type": "own-game",
                        "version": protection_version,
                        "key": str(evidence),
                    },
                )
                assert replay.status_code == 303
            from chess_coach.protection_followup_prior import prior

            with pytest.raises(ValueError):
                prior(db, LEARNER, "test", evidence, assessment_attempt)

        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="repeat",
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=fresh_item["reference"],
                assessment=True,
            )
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="foreign",
                subject="other",
                evidence_id=evidence,
                corpus_version="test",
                reference=reference,
            )
        review_evidence(db, evidence, decision="reject", actor="fixture")
        assert game_review(db, 1, LEARNER)[1] == {1}
        assert all(
            entry["status"] == "unavailable"
            for entry in protection_progress(db, LEARNER, "test")["items"]
        )
        with pytest.raises(ValueError):
            show(db, assessment_attempt, LEARNER)
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="stale",
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=reference,
            )
        with pytest.raises(ValueError):
            show(db, attempt, LEARNER)
        db.close()

    # Full-size ordering and uncertainty gates use synthetic, disjoint checks.
    from chess_coach.protection_progress_groups import group as progress_group

    progress_scope = (
        "test",
        "checksum",
        "white",
        chess.ROOK,
        chess.ROOK,
        "move_threatened_piece",
        6,
        0,
    )
    progress_checks = [
        {
            "attempt": str(i),
            "started_at": f"2026-01-01T00:{i:02d}:00+00:00",
            "answered_at": f"2026-01-01T00:{i:02d}:30+00:00",
            "current": True,
            "hints": 0,
            "status": "correct" if i < 10 else "incorrect",
            "outcome": "verified" if i < 10 else "incorrect",
        }
        for i in range(20)
    ]
    assert progress_group(progress_scope, progress_checks, False)["direction"] == "fewer"
    from chess_coach import protection_progress_game

    qualified = progress_group(progress_scope, progress_checks, False)
    assert qualified["answer_end"] == "2026-01-01T00:19:30+00:00"
    sample = {
        "games": 20,
        "eligible": 40,
        "oldest": "2026-01-02T00:00:00+00:00",
        "newest": "2026-01-03T00:00:00+00:00",
        "opportunities": 5,
        "played": 3,
        "other": 2,
        "opportunity_unresolved": 0,
        "unknown": 1,
        "unchecked": 0,
        "withheld_games": 0,
        "withheld_turns": 0,
    }
    games = {
        "comparable_reason": None,
        "bounds": {"status": "available"},
        "earlier": sample,
        "newer": sample,
    }
    progress_data = {"groups": [qualified], "items": [], "limited": False}
    with monkeypatch.context() as patch:
        patch.setattr(protection_progress_game, "practice_report", lambda *_: progress_data)
        patch.setattr(protection_progress_game, "game_report", lambda *_: games)
        page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"Both comparable game windows start after" in page.data
        assert b"<title>Unfamiliar protection assessments - Chess coach</title>" in page.data
        assert page.data.count(b"<h3>Independent protection-game windows</h3>") == 1
        assert (
            b"5 proved opportunities" in page.data
            and b"unresolved opportunity status: 1" in page.data
        )
        games["earlier"] = {**sample, "oldest": qualified["answer_end"]}
        page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"The more recent game window starts after" in page.data
        games["newer"] = {**sample, "oldest": qualified["answer_end"]}
        page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"game windows overlap, precede or tie" in page.data
        games["newer"] = {**sample, "oldest": None}
        page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"required date could not be verified" in page.data
        games["comparable_reason"] = "time_control_mismatch"
        page = client.get(
            "/plan/protection/progress", base_url="https://coach.invalid", headers=headers
        )
        assert b"sources and time controls are comparable" in page.data
    assert progress_group(progress_scope, progress_checks, True)["reason"]
    assert progress_group((*progress_scope[:-1], None), progress_checks, False)["reason"]
    progress_checks[9]["answered_at"] = progress_checks[10]["started_at"]
    assert progress_group(progress_scope, progress_checks, False)["reason"] == (
        "The assessment intervals overlap."
    )
    progress_checks[10]["started_at"] = progress_checks[9]["started_at"]
    assert progress_group(progress_scope, progress_checks, False)["reason"]
