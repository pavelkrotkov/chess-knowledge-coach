import json

from chess_coach.db import Database
from chess_coach.ontology import map_detector_facts, seed_ontology, skill_descendants


def test_seed_ontology_and_recursive_edges() -> None:
    db = Database(":memory:")
    db.initialize()

    assert seed_ontology(db, "test-1") >= 4
    descendants = skill_descendants(db, "tactics")

    assert "fork" in descendants
    assert "fork" in skill_descendants(db, "tactics", version="test-1")


def test_mapper_preserves_fact_provenance_and_operation() -> None:
    db = Database(":memory:")
    db.initialize()
    seed_ontology(db, "test-1")
    db.connection.execute(
        "INSERT INTO games (source_id, pgn, white, black, result) VALUES (?, ?, ?, ?, ?)",
        ("g1", "raw", "A", "B", "*"),
    )
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (?, ?, ?, ?, ?)",
        (game_id, 1, "8/8/8/8/8/8/8/4K3 w - - 0 1", "", ""),
    )
    position_id = db.connection.execute("SELECT id FROM positions").fetchone()[0]
    db.connection.execute(
        "INSERT INTO detector_facts(position_id, detector_version, fact_type, payload_json) VALUES (?, ?, ?, ?)",
        (position_id, "det-1", "fork", json.dumps({"motif": "fork"})),
    )
    db.connection.commit()

    result = map_detector_facts(db, "map-1", detector_version="det-1")
    again = map_detector_facts(db, "map-1", detector_version="det-1")

    assert len(result) == len(again) == 1
    assert result[0]["operation"] == "execute"
    assert result[0]["source_facts"]
    assert result[0]["mapper_version"] == "map-1"
