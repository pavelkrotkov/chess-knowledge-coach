from chess_coach.db import Database
from chess_coach.enrichment import (
    UnavailableMaiaAdapter,
    explain_position,
    predict_maia,
)


class FakeMaia:
    model = "maia-3"
    checkpoint = "checkpoint-1"

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]:
        assert fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        assert moves == ["e2e4"]
        assert elo == 1600
        return {"human_move": 0.7, "blunder": 0.1}


def test_maia_is_separate_and_explanation_is_facts_only(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result, white_elo, black_elo) VALUES (?, ?, ?, ?, ?, ?)",
        ('[Event "Test"]\n\n1. e4 *', "White", "Black", "*", 1500, 1600),
    )
    game_id = db.connection.execute("SELECT id FROM games").fetchone()[0]
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (?, ?, ?, ?, ?)",
        (game_id, 1, "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", "e4", "e2e4"),
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
    assert prediction["checkpoint"] == "checkpoint-1"
    assert prediction["adapter_version"] == "custom-0.1.0"
    stored = db.connection.execute(
        "SELECT model, checkpoint, adapter_version FROM maia_predictions WHERE position_id = ?",
        (position_id,),
    ).fetchone()
    assert tuple(stored) == ("maia-3", "checkpoint-1", "custom-0.1.0")
    assert prediction["probabilities"]["human_move"] == 0.7
    assert prediction["conditioning_elo"] == 1600
    assert "facts" in explanation["prompt_json"]
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0


def test_offline_mode_is_available_without_maia_dependency():
    assert predict_maia(None, 1, UnavailableMaiaAdapter()) is None


def test_subprocess_adapter_passes_context_and_preserves_checkpoint(monkeypatch):
    import json
    import subprocess

    from chess_coach.enrichment import SubprocessMaiaAdapter

    def run(args, *, input, text, capture_output, timeout, check):
        assert args == ["maia-test"]
        assert json.loads(input) == {"fen": "fen", "moves": ["e2e4"], "elo": 1600}
        assert text and capture_output and check and timeout == 12
        return subprocess.CompletedProcess(args, 0, stdout='{"e7e5": 1, "c7c5": 0.25}')

    monkeypatch.setattr(subprocess, "run", run)
    adapter = SubprocessMaiaAdapter(
        executable="maia-test", model="maia", checkpoint="sha256:test", timeout_seconds=12
    )
    assert adapter.predict("fen", ["e2e4"], 1600) == {"e7e5": 1.0, "c7c5": 0.25}
    assert adapter.checkpoint == "sha256:test"


def test_subprocess_adapter_rejects_bad_response_and_checkpoint(monkeypatch):
    import subprocess

    import pytest

    from chess_coach.enrichment import SubprocessMaiaAdapter

    for checkpoint in ("", "configured", "none"):
        with pytest.raises(ValueError, match="checkpoint"):
            SubprocessMaiaAdapter("maia-test", "maia", checkpoint)

    adapter = SubprocessMaiaAdapter("maia-test", "maia", "sha256:test")
    for payload, message in (
        ("not json", "invalid JSON"),
        ("[]", "non-object"),
        ('{"e2e4": true}', "invalid probability format"),
        ('{"e2e4": "0.5"}', "invalid probability format"),
        ('{"e2e4": NaN}', "finite values"),
        ('{"e2e4": 1.1}', "finite values"),
    ):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, _payload=payload, **kwargs: subprocess.CompletedProcess(
                args, 0, stdout=_payload
            ),
        )
        with pytest.raises(ValueError, match=message):
            adapter.predict("fen", [], None)


def test_custom_adapter_rejects_invalid_probabilities_without_storing_predictions():
    import pytest

    class InvalidMaia:
        model = "test-model"
        checkpoint = "test-checkpoint"

        def __init__(self, value):
            self.value = value

        def predict(self, fen, moves, elo):
            return self.value

    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('x', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, ?, 'e4', 'e2e4')",
        ("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",),
    )
    db.connection.commit()
    for value in ([], {"e2e4": True}, {"e2e4": "0.5"}, {"e2e4": float("nan")}, {"e2e4": -0.1}):
        with pytest.raises(ValueError, match="finite values"):
            predict_maia(db, 1, InvalidMaia(value))
    assert db.connection.execute("SELECT COUNT(*) FROM maia_predictions").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0
