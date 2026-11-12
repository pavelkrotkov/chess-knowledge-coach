"""A successful defense leads to a source-bound, playable transfer."""

import json
import sqlite3
import sys

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


def test_successful_protection_transfer_workflow(tmp_path, monkeypatch, capsys):
    from chess_coach.cli import main
    from chess_coach.web import create_app

    # A threatened piece may itself capture the attacker.
    fen = "4k3/8/8/2b5/3Q4/8/P7/7K w - - 0 1"
    features = protection_features(fen, ["d4c5"])
    assert features["mechanism"] == "move_threatened_piece"
    assert plausible(fen, ["d4c5"], features)

    for color in ("white", "black"):
        path = tmp_path / (color + ".sqlite")
        db = make_protection_game(path, monkeypatch, played="d4d5", color=color)
        evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('test','fixture','checksum','staging')"
        )
        corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
        setup = chess.Board("4k3/7p/8/2b5/3R4/8/P7/7K b - - 0 1")
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
        alternate = setup.copy()
        pawn_from, pawn_to = ("a2", "b2") if color == "white" else ("a7", "b7")
        pawn = alternate.remove_piece_at(chess.parse_square(pawn_from))
        alternate.set_piece_at(chess.parse_square(pawn_to), pawn)
        nonzero = "e8f8" if color == "white" else "e1f1"
        records += [
            ("w-unknown-history", setup.fen(), f"{nonzero} {moves[1]}"),
            ("x-wrong-role", setup.fen(), f"{moves[0]} {other}"),
            ("y-malformed", setup.fen(), f"{moves[0]} {moves[1]} invalid invalid"),
            ("z-match", setup.fen(), " ".join(moves)),
            ("z-second", alternate.fen(), " ".join(moves)),
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
        db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
        db.connection.commit()
        result = preview(db, LEARNER, evidence, "test")
        assert result["source_outcome"] == "success"
        assert len(result["items"]) == 2 and result["scanned"] == 125
        assert result["protection_scan"]["checked"] == 3
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
        assert moves[1] not in json.dumps(result)
        reference = result["items"][0]["reference"]
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
        assert json.loads(capsys.readouterr().out)["items"][0]["reference"] == reference

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
        assert reference.encode() in finder.data
        assert moves[1].encode() not in finder.data
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
        assert f"You play {color}".encode() in page.data and moves[1].encode() not in page.data
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
        assert (
            submit(db, attempt, LEARNER, event_id="move", move=moves[1])["status"]
            == "line_completed"
        )

        # A different still-unfamiliar candidate supports an independently checked first move.
        fresh = preview(db, LEARNER, evidence, "test")
        assert len(fresh["items"]) == 1 and fresh["items"][0]["assessment_available"]
        assessment = client.post(
            url,
            base_url="https://coach.invalid",
            headers=headers | {"Origin": "https://coach.invalid"},
            data={"csrf": csrf, "reference": fresh["items"][0]["reference"], "assessment": "1"},
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
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="repeat",
                subject=LEARNER,
                evidence_id=evidence,
                corpus_version="test",
                reference=fresh["items"][0]["reference"],
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
