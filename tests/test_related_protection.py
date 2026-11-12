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
        pawn_from = "a2" if color == "white" else "a7"
        alternatives = []
        for file in ("b", "c", "e", "g"):
            alternate = setup.copy()
            pawn = alternate.remove_piece_at(chess.parse_square(pawn_from))
            alternate.set_piece_at(chess.parse_square(file + pawn_from[1]), pawn)
            alternatives.append(alternate)
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
        assert len(result["items"]) == 4 and result["scanned"] == 128
        assert result["protection_scan"]["checked"] == 6
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
        assert json.dumps(moves[1]) not in json.dumps(result)
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
        assert len(fresh["items"]) == 4 and fresh["items"][0]["assessment_available"]
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

        from chess_coach.protection_plan_history import report as assessment_history

        history = assessment_history(db, LEARNER, "test", evidence)
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
            assert db.connection.execute("PRAGMA data_version").fetchone()[0] == version
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
            db.connection.execute(
                "UPDATE unified_sessions SET started_at='2099-01-01T00:00:00+00:00' WHERE attempt_id=?",
                ("verified-miss",),
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
