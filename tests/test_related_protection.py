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
        records += [
            ("x-wrong-role", setup.fen(), f"{moves[0]} {other}"),
            ("y-malformed", setup.fen(), f"{moves[0]} {moves[1]} invalid invalid"),
            ("z-match", setup.fen(), " ".join(moves)),
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
        assert len(result["items"]) == 1 and result["scanned"] == 123
        assert result["protection_scan"]["checked"] == 2
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
        source = client.get(
            f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
        )
        assert b"Find related protection practice" in source.data
        page = client.get(
            f"/evidence/{evidence}/related-protections",
            base_url="https://coach.invalid",
            headers=headers,
        )
        assert b"successful defense rehearsal" in page.data
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
