"""A lesson must never present a non-canonical or illegal continuation."""

import chess

from chess_coach.lesson_lines import legal_san


def test_legal_san_requires_a_complete_canonical_line():
    fen = chess.STARTING_FEN
    assert legal_san(fen, ["e4", "e5", "Nf3"]) == ["e4", "e5", "Nf3"]
    assert legal_san(fen, ["e4", "e5", "Nf6"]) is None
    assert legal_san(fen, ["e2e4"]) is None
    assert legal_san("invalid", ["e4"]) is None
    assert legal_san(fen, []) is None


def test_representatives_deduplicate_game_identity(monkeypatch):
    from chess_coach.lesson_examples import representatives

    monkeypatch.setattr("chess_coach.lesson_examples.context", lambda _: {"side": "white"})

    items = [
        {"id": n, "game_key": key, "game_id": n, "position_id": n, "ply": n, "decision": {}}
        for n, key in enumerate(("a", "a", "b", "c", "d"), 1)
    ]
    assert [item["id"] for item in representatives(items, limit=3)] == [1, 3, 4]


def test_lesson_source_rechecks_ownership_and_currentness(monkeypatch):
    import chess_coach.lesson_source as module

    evidence = {
        "id": 1,
        "position_id": 2,
        "subject": "learner",
        "mapping_producer": "fork-opportunity-mapper",
        "fork_source_currentness": "current",
        "review_status": "unreviewed",
    }
    monkeypatch.setattr(module, "inspect_evidence", lambda *_: evidence)
    monkeypatch.setattr(module, "supported", lambda *_: True)
    monkeypatch.setattr(module, "evidence_row", lambda *_: {})
    monkeypatch.setattr(module, "review", lambda *_: "unreviewed")
    monkeypatch.setattr(module, "inspect_decision", lambda *_, **__: {"played_san": "e4"})
    candidate = {"id": 1, "position_id": 2}
    assert module.source(None, "learner", candidate)["decision"]["played_san"] == "e4"
    assert module.source(None, "other", candidate) is None
    evidence["fork_source_currentness"] = "stale"
    assert module.source(None, "learner", candidate) is None
    evidence["fork_source_currentness"] = "current"
    evidence["review_status"] = "rejected"
    assert module.source(None, "learner", candidate) is None
