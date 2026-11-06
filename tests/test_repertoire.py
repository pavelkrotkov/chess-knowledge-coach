"""Behavioral coverage of the private, descriptive repertoire."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.openings import import_openings
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import game_input
from chess_coach.pipeline_opening import run_opening
from chess_coach.repertoire import game_detail, repertoire_report
from chess_coach.repertoire_sources import games_for_learner
from chess_coach.web import create_app


def game(white, black, moves, result="1-0", *, second=None):
    timestamp = (
        f'[UTCDate "2026.01.01"]\n[UTCTime "00:00:{second:02}"]\n' if second is not None else ""
    )
    return f'''{timestamp}[Event "Fixture"]
[White "{white}"]
[Black "{black}"]
[Result "{result}"]
[TimeControl "600+0"]
[WhiteElo "1500"]
[BlackElo "1600"]

{moves} {result}
'''


def test_repertoire_transpositions_colors_refresh_and_privacy(tmp_path, monkeypatch):
    path = tmp_path / "test.sqlite"
    db = Database(path)
    db.initialize()
    for text in (
        game("Learner", "Opponent", "1. d4 d5 2. Nf3 Nf6 3. c4", second=3),
        game("Learner", "Opponent", "1. Nf3 Nf6 2. d4 d5 3. g3", "0-1", second=3),
        game("Opponent", "Learner", "1. d4 d5 2. Nf3 Nf6", second=2),
        game("Other", "Opponent", "1. d4 d5 2. Nf3 Nf6", second=6),
        game("Learner", "Opponent", "1. e4 e5", "*", second=1),
        game("Learner", "Opponent", "1. c4 e5"),
        game("Learner", "Opponent", "1. Nf3 d5", second=70),
    ):
        ingest_pgn(db, text)
    source = tmp_path / "opening.tsv"
    source.write_text(
        "eco\tname\tmoves\nD00\tTest\td4 d5 Nf3 Nf6\nA04\tAlternate\tNf3 Nf6 d4 d5\nD20\tOther\td4 Nf6 c4\nD30\tC line\td4 d5 Nf3 Nf6 c4\nA10\tG line\tNf3 Nf6 d4 d5 g3\n"
    )
    import_openings(db, source, version="test", source_url="cc0://test")
    config = PipelineConfig(
        learner="learner",
        opening_version="test",
        opening_source="cc0://test",
        classifier_version="1.1.0",
    )
    for game_id in (1, 2, 3, 5):
        assert run_opening(db, game_id, game_input(db, game_id), config)["status"] == "complete"
    db.connection.execute("UPDATE style_game_times SET status='stale' WHERE game_id=4")
    report = repertoire_report(db, "learner")
    assert [g["id"] for g in report["games"]] == [2, 1, 3, 5]
    assert report["games"][0]["played_at"] == "2026-01-01T00:00:03+00:00"
    assert report["games"][0]["date"] == game_detail(db, "learner", 2)["date"]
    assert report["unknown"] == 1
    assert report["time_coverage"]["unknown_time_lower_bound"] == 2
    assert report["time_coverage"]["unknown_ownership_global_lower_bound"] == 1
    assert [row["id"] for row, _ in games_for_learner(db, "learner")[0]] == [7, 6, 5, 3, 2, 1]
    monkeypatch.setattr("chess_coach.repertoire.MAX_GAMES", 1)
    limited = repertoire_report(db, "learner")
    assert [g["id"] for g in limited["games"]] == [2]
    assert limited["game_limit_reached"] and limited["time_coverage"]["boundary_tie"]
    monkeypatch.undo()
    white = next(g for g in report["groups"] if g["color"] == "white" and len(g["lines"]) == 2)
    assert white["count"] == 2 and len(white["lines"]) == 2
    assert white["outcomes"] == {"win": 1, "loss": 1}
    black = next(g for g in report["groups"] if g["color"] == "black" and g["names"])
    assert black["count"] == 1 and black["outcomes"] == {"loss": 1}
    assert game_detail(db, "learner", 1)["learner_rating"] == 1500
    from chess_coach.opening_decision import inspect as inspect_opening

    monkeypatch.setattr("chess_coach.opening_decision_budget.VERSION", "test")
    monkeypatch.setattr("chess_coach.opening_decision_budget.SOURCE", "cc0://test")
    from chess_coach.classification_inputs import opening_graph, opening_input, position_input
    from chess_coach.fact_fingerprint import canonical, digest

    dataset_id = db.connection.execute(
        "SELECT id FROM opening_datasets WHERE version=?", ("test",)
    ).fetchone()[0]
    graph = opening_graph(db, dataset_id)
    monkeypatch.setattr(
        "chess_coach.opening_decision_budget.GRAPH_SHA256", digest(canonical(graph))
    )
    old_payload = {
        "positions": position_input(db, 1),
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }
    assert opening_input(db, 1, dataset_id) == digest(canonical(old_payload))
    assert opening_input(db, 1, dataset_id, graph=graph) == digest(canonical(old_payload))
    first_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=1"
    ).fetchone()[0]
    transposed_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=1"
    ).fetchone()[0]
    black_move = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=3 AND ply=2"
    ).fetchone()[0]
    first = inspect_opening(db, 1, first_move, "learner")
    transposed = inspect_opening(db, 2, transposed_move, "learner")
    black_choice = inspect_opening(db, 3, black_move, "learner")
    assert first["played"] == "d4" and transposed["played"] == "Nf3"
    assert first["catalog"]["parent"] == transposed["catalog"]["parent"]
    from chess_coach.opening_decision_source import source as opening_source

    after_first = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=5"
    ).fetchone()[0]
    after_second = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 AND ply=5"
    ).fetchone()[0]
    branch_first = inspect_opening(db, 1, after_first, "learner")
    branch_second = inspect_opening(db, 2, after_second, "learner")
    assert branch_first["catalog"]["parent"] == branch_second["catalog"]["parent"]
    assert "g3" in [item["san"] for item in branch_first["catalog"]["items"]]
    assert "c4" in [item["san"] for item in branch_second["catalog"]["items"]]
    board_first = opening_source(db, 1, after_first, "learner")[2]
    board_second = opening_source(db, 2, after_second, "learner")[2]
    assert len(board_first.move_stack) == len(board_second.move_stack) == 4
    assert board_first.move_stack != board_second.move_stack
    assert "Nf3" in [item["san"] for item in first["catalog"]["items"]]
    assert "d4" in [item["san"] for item in transposed["catalog"]["items"]]
    assert black_choice["color"] == "black" and black_choice["played"] == "d5"
    assert "Nf6" in [item["san"] for item in black_choice["catalog"]["items"]]
    assert first["analysis"]["status"] == "current analysis unavailable"
    with pytest.raises(ValueError, match="unavailable"):
        inspect_opening(db, 3, first_move, "learner")
    with pytest.raises(ValueError, match="unavailable"):
        inspect_opening(db, 1, first_move, "other")
    db.connection.execute("UPDATE opening_datasets SET content_revision=2 WHERE version='test'")
    with pytest.raises(ValueError, match="pinned"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.execute("UPDATE opening_datasets SET content_revision=1 WHERE version='test'")
    db.connection.commit()
    # The bounded graph and fingerprint share a short snapshot, not the game replay.
    import chess_coach.opening_decision_budget as opening_budget
    import chess_coach.opening_decision_source as opening_source_module

    graph_reader = opening_budget.opening_graph
    history_reader = opening_source_module._history

    def checked_graph(database, selected_dataset):
        assert database.connection.in_transaction
        return graph_reader(database, selected_dataset)

    def checked_history(database, *args):
        assert not database.connection.in_transaction
        return history_reader(database, *args)

    with monkeypatch.context() as patch:
        patch.setattr(opening_budget, "opening_graph", checked_graph)
        patch.setattr(opening_source_module, "_history", checked_history)
        assert inspect_opening(db, 1, first_move, "learner")["played"] == "d4"

    original_fen = db.connection.execute(
        "SELECT fen FROM positions WHERE id=?", (first_move,)
    ).fetchone()[0]
    db.connection.execute("UPDATE positions SET fen=? WHERE id=?", (original_fen + " ", first_move))
    with pytest.raises(ValueError, match="stale"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.rollback()
    import chess

    from chess_coach.opening_decision_catalog import catalog

    dataset_id = first["opening"]["dataset_id"]
    db.connection.execute(
        "INSERT INTO opening_edges(dataset_id,parent_key,child_key,uci) VALUES(?,?,?,?)",
        (dataset_id, first["catalog"]["parent"], "invalid-child", "a1a8"),
    )
    filtered = catalog(db, dataset_id, chess.Board(), "d2d4")
    assert "a1a8" not in [item["uci"] for item in filtered["items"]]
    from chess_coach.opening_classification import classify_game

    classify_game(db, 1, version="test", source_url="cc0://test")
    with pytest.raises(ValueError, match="pinned opening graph differs"):
        inspect_opening(db, 1, first_move, "learner")
    db.connection.rollback()
    with pytest.raises(ValueError, match="unavailable"):
        game_detail(db, "learner", 4)
    app = create_app(
        db_path=path,
        subject="learner",
        actor="reviewer",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    game_page = client.get("/repertoire/games/1", base_url="https://coach.invalid", headers=headers)
    assert b"Explore opening alternatives" in game_page.data
    route = f"/repertoire/games/1/openings/{first_move}"
    assert client.get(route, base_url="https://coach.invalid").status_code == 403
    for invalid in (0, 2**63):
        assert (
            client.get(
                f"/repertoire/games/{invalid}/openings/{first_move}",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/repertoire/games/1/openings/{invalid}",
                base_url="https://coach.invalid",
                headers=headers,
            ).status_code
            == 404
        )
    response = client.get(route, base_url="https://coach.invalid", headers=headers)
    assert response.status_code == 200 and b"Nf3" in response.data
    assert b"No qualified same-search comparison" in response.data

    def sample_comparison(_db, _learner, _context, _board, items):
        items[0]["analysis"] = {"played": 5, "alternative": 10, "depth": 8, "line": ["Nf3"]}
        return {
            "status": "available",
            "engine": "Fixture",
            "engine_version": "1",
            "run_id": 1,
            "limits": {"nodes": 1000},
        }

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.opening_decision.comparison", sample_comparison)
        compared = client.get(route, base_url="https://coach.invalid", headers=headers)
        assert compared.status_code == 200 and b"Played 5 cp; alternative 10 cp" in compared.data
        assert b"Recorded continuation: Nf3" in compared.data
    assert (
        client.get(
            f"/repertoire/games/4/openings/{first_move}",
            base_url="https://coach.invalid",
            headers=headers,
        ).status_code
        == 404
    )
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
    response = client.get("/repertoire", base_url="https://coach.invalid", headers=headers)
    assert response.status_code == 200
    assert b"New" in response.data and b"/repertoire/games/5" in response.data
    assert b"Structure coverage:" in response.data
    assert response.data.count(b"played 2026-01-01T00:00:01+00:00") >= 2
    assert b"Games with known ownership and no verified start time: at least 2" in response.data
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
    # Recompute the checked-in graph pin from the checksum-verified bundled data.
    from chess_coach.opening_snapshot import GRAPH_SHA256, import_snapshot

    reference = Database(":memory:")
    reference.initialize()
    assert import_snapshot(reference) == 3865
    reference_id = reference.connection.execute("SELECT id FROM opening_datasets").fetchone()[0]
    assert digest(canonical(opening_graph(reference, reference_id))) == GRAPH_SHA256
    reference.close()
