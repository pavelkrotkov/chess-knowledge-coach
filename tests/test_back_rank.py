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
    from chess_coach.coaching_practice import choices
    from chess_coach.lesson_mechanisms import describe
    from chess_coach.lesson_source import source
    from chess_coach.objective_defense_source import VERSION as DEFENSE_VERSION
    from chess_coach.unified_session_events import reveal, show, submit
    from chess_coach.unified_sessions import start

    failure_db = owned_game(
        tmp_path / "coaching-defense.sqlite", monkeypatch, fen=DEFENSE, move="Nb6"
    )
    process_mate(failure_db, 1, "fixture_a")
    process_decision(failure_db, 1, "fixture_a")
    evidence = failure_db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='back_rank' AND operation='prevent'"
    ).fetchone()[0]
    inspected = source(failure_db, "fixture_a", {"id": evidence, "position_id": 1})
    assert inspected is not None and inspected["evidence"]["outcome"] == "failure"
    fact = inspected["evidence"]["facts"][0]
    example = describe(inspected)
    lesson = {
        "skill": "back_rank",
        "operation": "prevent",
        "family": inspected["evidence"]["mapping_producer"],
        "source_version": fact["detector_version"],
        "examples": [dict(example, evidence_id=0), example],
    }
    selected = choices(failure_db, "fixture_a", {"groups": [{"lesson": lesson}]})[0]
    assert selected["version"] == DEFENSE_VERSION and selected["key"] == str(evidence)
    assert selected["kind"] == "back_rank_defense"
    state = start(
        failure_db,
        attempt_id="defense",
        subject="fixture_a",
        source_type="own-game",
        version=selected["version"],
        key=selected["key"],
    )
    assert state["objective"] == "avoid_immediate_mate"
    failure_db.connection.execute(
        "UPDATE pipeline_stages SET status='pending' WHERE stage='analysis'"
    )
    failure_db.connection.commit()
    assert choices(failure_db, "fixture_a", {"groups": [{"lesson": lesson}]}) == [None]
    failure_db.close()

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

    db.close()
    for black in (False, True):
        _related_defense_workflow(monkeypatch, black)


def _related_defense_workflow(monkeypatch, black):
    import contextlib
    import io
    import json
    import re

    import chess

    from chess_coach import web_related_backrank as web
    from chess_coach.cli_parser import build_parser
    from chess_coach.cli_related_commands import COMMANDS
    from chess_coach.evidence_review import inspect_evidence
    from chess_coach.lesson_mechanisms import describe
    from chess_coach.lesson_source import source
    from chess_coach.related_backrank_defense import preview, start_related
    from chess_coach.unified_session_events import show, submit
    from chess_coach.web import create_app

    with monkeypatch.context() as patch:
        fen = chess.Board(DEFENSE).mirror().fen() if black else DEFENSE
        subject, bad = ("fixture_b", "Nb3") if black else ("fixture_a", "Nb6")
        db = owned_game(":memory:", patch, fen=fen, move=bad)
        process_mate(db, 1, subject)
        process_decision(db, 1, subject)
        evidence = db.connection.execute(
            "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?",
            ("back_rank", "prevent"),
        ).fetchone()[0]
        assert inspect_evidence(db, evidence)["backrank_defense_transfer"]
        assert describe(source(db, subject, {"id": evidence, "position_id": 1}))[
            "backrank_defense_transfer"
        ]
        db.connection.execute(
            "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES(?,?,?,?)",
            ("test", "fixture", "checksum", "staging"),
        )
        corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
        board = chess.Board(DEFENSE)
        board.turn = chess.BLACK
        board.set_piece_at(chess.H7, chess.Piece(chess.PAWN, chess.BLACK))
        if black:
            board = board.mirror()
        setup, good, wrong = ("h2h3", "g7g6", "c5b3") if black else ("h7h6", "g2g3", "c4b6")
        for key, move in (("good", good), ("wrong", wrong)):
            db.connection.execute(
                """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
                rating_deviation,themes_json,objective) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    key,
                    corpus,
                    board.fen(),
                    "https://example.invalid",
                    setup + " " + move,
                    1200,
                    80,
                    "[]",
                    "unknown",
                ),
            )
            db.connection.execute(
                "INSERT INTO puzzle_themes VALUES(?,?,?,?)", (corpus, key, "defensiveMove", 1200)
            )
        db.connection.execute("UPDATE puzzle_corpora SET state=?", ("ready",))
        db.connection.commit()
        transfer = preview(db, subject, evidence, "test")
        assert len(transfer["items"]) == 1 and transfer["defense_scan"]["proofs"] == 2
        assert "defense_witness" not in transfer["items"][0]
        with pytest.raises(ValueError):
            start_related(
                db,
                attempt_id="bad",
                subject=subject,
                evidence_id=evidence,
                corpus_version="test",
                reference="tampered",
            )

        patch.setattr(web, "database", lambda: db)
        app = create_app(
            db_path=":memory:",
            subject=subject,
            actor="fixture",
            corpus="test",
            login="fixture",
            origin="https://coach.invalid",
        )
        client = app.test_client()
        headers = {"Tailscale-User-Login": "fixture"}
        url = f"/evidence/{evidence}/related-backrank-defenses"
        assert client.get(url).status_code == 403
        page = client.get(url, base_url="https://coach.invalid", headers=headers)
        assert page.status_code == 200 and b"Practice this defense" in page.data
        assert not re.search(
            rb"(?<![A-Za-z0-9_-])" + good.encode() + rb"(?![A-Za-z0-9_-])", page.data
        )
        parser = build_parser()
        args = parser.parse_args(
            [
                "related-backrank-defenses",
                "--subject",
                subject,
                "--evidence",
                str(evidence),
                "--corpus",
                "test",
            ]
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            COMMANDS[args.command](db, args)
        listing = json.loads(output.getvalue())
        assert len(listing["items"]) == 1

        if black:
            args = parser.parse_args(
                [
                    "start-related-backrank-defense",
                    "--subject",
                    subject,
                    "--evidence",
                    str(evidence),
                    "--corpus",
                    "test",
                    "--attempt",
                    "cli-defense",
                    "--reference",
                    listing["items"][0]["reference"],
                ]
            )
            with contextlib.redirect_stdout(io.StringIO()):
                COMMANDS[args.command](db, args)
            attempt = "cli-defense"
        else:
            with client.session_transaction(base_url="https://coach.invalid") as session:
                csrf = session["csrf"]
            response = client.post(
                url + "/start",
                base_url="https://coach.invalid",
                headers=headers | {"Origin": "https://coach.invalid"},
                data={"csrf": csrf, "reference": transfer["items"][0]["reference"]},
            )
            assert response.status_code == 303
            attempt = response.location.rsplit("/", 1)[-1]
        state = show(db, attempt, subject)
        assert state["status"] == "active" and "backrank_defense_witness" not in state
        done = submit(db, attempt, subject, event_id="answer", move=good)
        assert done["status"] == "line_completed" and "backrank_defense_witness" in done
        review_evidence(db, evidence, decision="reject", actor="fixture")
        with pytest.raises(ValueError):
            show(db, attempt, subject)
        db.close()
