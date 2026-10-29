"""Behavioral coverage of the private, descriptive repertoire."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.opening_snapshot import SOURCE, VERSION, import_snapshot
from chess_coach.openings import classify_game, import_openings
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import game_input
from chess_coach.pipeline_opening import run_opening
from chess_coach.repertoire import game_detail, repertoire_report
from chess_coach.web import create_app


def game(white, black, moves, result="1-0"):
    return f'''[Event "Fixture"]
[White "{white}"]
[Black "{black}"]
[Result "{result}"]
[TimeControl "600+0"]
[WhiteElo "1500"]
[BlackElo "1600"]

{moves} {result}
'''


def test_repertoire_transpositions_colors_refresh_and_privacy(tmp_path):
    path = tmp_path / "test.sqlite"
    db = Database(path)
    db.initialize()
    for text in (
        game("Learner", "Opponent", "1. d4 d5 2. Nf3 Nf6"),
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5", "0-1"),
        game("Opponent", "Learner", "1. d4 d5 2. Nf3 Nf6"),
        game("Other", "Opponent", "1. d4 d5 2. Nf3 Nf6"),
        game("Learner", "Opponent", "1. e4 e5", "*"),
    ):
        ingest_pgn(db, text)
    source = tmp_path / "opening.tsv"
    source.write_text("eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\n")
    import_openings(db, source, version="test", source_url="cc0://test")
    config = PipelineConfig(
        learner="learner",
        opening_version="test",
        opening_source="cc0://test",
        classifier_version="1.1.0",
    )
    for game_id in (1, 2, 3, 5):
        assert run_opening(db, game_id, game_input(db, game_id), config)["status"] == "complete"
    report = repertoire_report(db, "learner")
    assert len(report["games"]) == 4 and report["unknown"] == 1
    white = next(g for g in report["groups"] if g["color"] == "white" and len(g["lines"]) == 2)
    assert white["count"] == 2 and len(white["lines"]) == 2
    assert white["outcomes"] == {"win": 1, "loss": 1}
    black = next(g for g in report["groups"] if g["color"] == "black" and g["names"])
    assert black["count"] == 1 and black["outcomes"] == {"loss": 1}
    assert game_detail(db, "learner", 1)["learner_rating"] == 1500
    with pytest.raises(ValueError, match="unavailable"):
        game_detail(db, "learner", 4)
    source.write_text("eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\nC20\tNew\te4 e5\n")
    import_openings(db, source, version="test", source_url="cc0://test")
    assert repertoire_report(db, "learner")["stale"] == 4
    assert run_opening(db, 5, game_input(db, 5), config)["status"] == "complete"
    assert game_detail(db, "learner", 5)["opening"]["name"] == "New"
    assert (
        db.connection.execute("SELECT COUNT(*) FROM opening_runs WHERE game_id=5").fetchone()[0]
        == 2
    )
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/repertoire", base_url="https://coach.invalid").status_code == 403
    headers = {"Tailscale-User-Login": "login"}
    assert (
        client.get("/repertoire", base_url="https://coach.invalid", headers=headers).status_code
        == 200
    )
    assert (
        client.get(
            "/repertoire/games/1", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/repertoire/games/4", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )


def test_empty_repertoire_and_official_snapshot():
    db = Database(":memory:")
    db.initialize()
    report = repertoire_report(db, "learner")
    assert not report["games"] and not report["groups"] and report["dataset"] is None
    assert import_snapshot(db) == 3865
    assert db.connection.execute("SELECT version,source_url FROM opening_datasets").fetchone()[
        :
    ] == (VERSION, SOURCE)
    ingest_pgn(db, game("Learner", "Opponent", "1. e4 e5 2. Nf3 Nc6 3. Bb5"))
    assert classify_game(db, 1, version=VERSION, source_url=SOURCE)["matched"]


def test_latest_reached_position_wins_over_canonical_ply(tmp_path):
    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, game("Learner", "Opponent", "1. Nf3 Nf6 2. Ng1 Ng8 3. e4 e5 4. Nf3"))
    source = tmp_path / "names.tsv"
    source.write_text(
        "eco\tname\tmoves\nC20\tEarlier\tNf3 Nf6 Ng1 Ng8 e4 e5\nC40\tLater\te4 e5 Nf3\n"
    )
    import_openings(db, source, version="v", source_url="cc0://test")
    assert classify_game(db, 1, version="v", source_url="cc0://test")["name"] == "Later"


def test_recurring_links_require_current_accepted_failures():
    from chess_coach.evidence_review import review_evidence

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, game("Learner", "Opponent", "1. e4 e5"))
    ingest_pgn(db, game("Opponent", "Learner", "1. d4 d5"))
    for game_id in (1, 2):
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=? AND ply=?", (game_id, game_id)
        ).fetchone()[0]
        run = db.connection.execute(
            """INSERT INTO mapping_runs(producer,position_id,subject,operation,scope_key,
            mapper_version,input_json,input_hash,output_hash,created_at,status)
            VALUES('fixture',?,'learner','execute','fixture','1','{}',?,?,'2026-01-01','active')""",
            (position, str(game_id), str(game_id)),
        ).lastrowid
        db.connection.execute(
            """INSERT INTO evidence_mappings(position_id,skill,operation,outcome,confidence,
            subject,mapping_run_id) VALUES(?,'fork','execute','failure',1,'learner',?)""",
            (position, run),
        )
    db.connection.commit()
    review_evidence(db, 1, decision="accept", actor="reviewer")
    assert not repertoire_report(db, "learner")["recurring"]
    review_evidence(db, 2, decision="accept", actor="reviewer")
    assert len(repertoire_report(db, "learner")["recurring"][0]["evidence"]) == 2
    review_evidence(db, 2, decision="revoke", actor="reviewer")
    assert not repertoire_report(db, "learner")["recurring"]
