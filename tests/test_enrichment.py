from chess_coach.db import Database
from chess_coach.enrichment import (
    UnavailableMaiaAdapter,
    explain_position,
    predict_maia,
)


class FakeMaia:
    model = "maia-3"
    checkpoint = "checkpoint-1"

    def predict(self, fen: str, moves: list[str]) -> dict[str, float]:
        assert fen == "fen"
        assert moves == ["e2e4"]
        return {"human_move": 0.7, "blunder": 0.1}


def test_maia_is_separate_and_explanation_is_facts_only(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES (?, ?, ?, ?)",
        ('[Event "Test"]\n\n1. e4 *', "White", "Black", "*"),
    )
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (?, ?, ?, ?, ?)",
        (game_id, 1, "fen", "e4", "e2e4"),
    )
    position_id = db.connection.execute("SELECT id FROM positions").fetchone()[0]
    db.connection.commit()

    prediction = predict_maia(db, position_id, FakeMaia())
    explanation = explain_position(
        db,
        position_id,
        facts={"prediction": prediction, "evidence": ["fact-1"]},
        generator=lambda facts: "Explain only these facts: " + str(facts),
    )

    assert prediction is not None
    assert prediction["model"] == "maia-3"
    assert prediction["probabilities"]["human_move"] == 0.7
    assert "facts" in explanation["prompt_json"]
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0


def test_offline_mode_is_available_without_maia_dependency():
    assert predict_maia(None, 1, UnavailableMaiaAdapter()) is None
