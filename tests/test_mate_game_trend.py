"""Complete mate-in-one cohorts, provenance, and coverage gates."""

import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.mate_game_trend import report
from chess_coach.style_time_projection import update_projection
from chess_coach.web import create_app
from tests.test_mate_proof import FEN


def pgn(second, move, event="Synthetic", dated=True):
    date = f'[UTCDate "2026.01.01"]\n[UTCTime "00:00:{second:02}"]\n' if dated else ""
    return f'''[Event "{event}"]
[White "fixture_a"]
[Black "fixture_b"]
{date}[SetUp "1"]
[FEN "{FEN}"]
[Result "1-0"]

1. {move} 1-0
'''


def test_complete_private_samples_and_unavailable_coverage(tmp_path):
    path = tmp_path / "games.sqlite"
    db = Database(path)
    db.initialize()
    for i in range(41):
        ingest_pgn(db, pgn(i, "Qg1" if i % 2 else "Qg7#"))
    ingest_pgn(db, pgn(40, "Qg7#", event="Duplicate import"))
    before = db.connection.total_changes
    result = report(db, "fixture_a")
    assert db.connection.total_changes == before
    assert result["comparable"]
    assert result["duplicates"] == 1 and result["unavailable"] == 0
    assert result["newer"]["games"] == result["earlier"]["games"] == 20
    assert result["newer"]["opportunities"] == result["earlier"]["opportunities"] == 20
    assert result["newer"]["misses"] == result["earlier"]["misses"] == 10
    assert result["newer"]["miss_games"] == 10
    assert result["newer"]["newest"].startswith("2026-01-01T00:00:40")
    assert result["earlier"]["oldest"].startswith("2026-01-01T00:00:01")

    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    url = "/game-samples/mate-in-one"
    assert client.get(url, base_url="https://coach.invalid").status_code == 403
    page = client.get(
        url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert page.status_code == 200 and b"10 missed of 20" in page.data
    assert b"/decisions/" in page.data and b"practice attempts are not included" in page.data
    assert b"fixture_a" not in page.data and b"fixture_b" not in page.data
    inspection = client.get(
        "/games/1/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert inspection.status_code == 200
    assert b"1 eligible turns; 1 fully checked" in inspection.data
    assert b"immediate mate" in inspection.data and b"miss rate is unavailable" in inspection.data
    assert (
        client.get(
            "/games/9223372036854775808/short-mate",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        ).status_code
        == 400
    )
    app.config["SUBJECT"] = "fixture_c"
    assert (
        client.get(
            "/games/1/short-mate",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        ).status_code
        == 400
    )
    app.config["SUBJECT"] = "default"
    unavailable = client.get(
        url, base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert unavailable.status_code == 400 and b"Learner identity is unavailable" in unavailable.data
    app.config["SUBJECT"] = "fixture_a"

    ingest_pgn(db, pgn(0, "Qg1", event="Unknown date", dated=False))
    uncertain = report(db, "fixture_a")
    assert not uncertain["comparable"]
    assert uncertain["coverage"]["unknown_time_lower_bound"] == 1

    db.connection.execute("DELETE FROM games WHERE id=(SELECT MAX(id) FROM games)")
    db.connection.commit()
    game = db.connection.execute("SELECT id,pgn FROM games WHERE pgn LIKE '%00:00:20%'").fetchone()
    db.connection.execute(
        "UPDATE games SET pgn=? WHERE id=?",
        (game["pgn"].replace("00:00:20", "00:00:21"), game["id"]),
    )
    update_projection(db.connection, game["id"])
    db.connection.commit()
    assert not report(db, "fixture_a")["comparable"]
    db.close()


def test_unfinished_and_automatic_terminal_games_are_unavailable(tmp_path):
    from chess_coach.mate_game_sample import prepared_game

    db = Database(tmp_path / "unfinished.sqlite")
    db.initialize()
    unfinished = pgn(1, "Qg1").replace("1-0", "*")
    ingest_pgn(db, unfinished)
    game = db.connection.execute("SELECT * FROM games").fetchone()
    import pytest

    with pytest.raises(ValueError, match="unfinished"):
        prepared_game(db, game, "fixture_a")
    db.close()

    db = Database(tmp_path / "terminal.sqlite")
    db.initialize()
    ingest_pgn(db, pgn(1, "Qg1").replace("0 1", "150 1"))
    game = db.connection.execute("SELECT * FROM games").fetchone()
    with pytest.raises(ValueError, match="game termination"):
        prepared_game(db, game, "fixture_a")
    db.close()


def test_result_contradicting_checkmate_is_unavailable(tmp_path):
    import pytest

    from chess_coach.mate_game_sample import prepared_game

    db = Database(tmp_path / "contradiction.sqlite")
    db.initialize()
    ingest_pgn(db, pgn(1, "Qg7#").replace("1-0", "0-1"))
    game = db.connection.execute("SELECT * FROM games").fetchone()
    with pytest.raises(ValueError, match="contradicts"):
        prepared_game(db, game, "fixture_a")
    db.close()


def test_short_mate_background_samples_resume_and_detect_changes(tmp_path, monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace

    from chess_coach import short_mate_trend_paths as mate_paths
    from chess_coach import short_mate_trend_scan as scan
    from chess_coach import short_mate_trend_turns as turns
    from chess_coach.short_mate_trend_cohort import signature as source_signature
    from chess_coach.short_mate_trend_paths import binding, location
    from chess_coach.short_mate_trend_report import report as cached_report
    from chess_coach.short_mate_trend_select import _item
    from chess_coach.short_mate_trend_store import read, write

    # A complete rotation visits every game and returns to the newest one.
    cursor = 0
    visited = []
    for _ in range(40):
        visited.append(cursor)
        cursor = scan._next(cursor, 40)
    assert len(set(visited)) == 40 and cursor == 0

    # An overall interruption leaves the turn for the next activation; a local
    # proof timeout becomes a terminal unknown so it cannot stall the scan.
    with monkeypatch.context() as patch:
        source = {
            "signature": "source",
            "pairs": [({"subject": True, "played_move": "a1a2", "position_id": 1}, None)],
        }
        patch.setattr(turns, "prepare", lambda *args: source)
        patch.setattr(turns, "recheck", lambda *args: None)
        patch.setattr(turns, "fingerprint", lambda value: value)
        patch.setattr(turns, "classify", lambda *args: ("unknown", "deadline"))
        item = {"id": 1, "signature": "source", "results": []}
        times = iter([0.0, 1.6])
        patch.setattr(turns, "time", SimpleNamespace(monotonic=lambda: next(times)))
        assert turns.inspect(None, "fixture_a", item, 2.0, 1) == 0
        assert not item["results"]
        times = iter([0.0, 0.0])
        assert turns.inspect(None, "fixture_a", item, 2.0, 1) == 1
        assert item["results"] == [[1, "unknown", "turn_deadline"]]

    root = tmp_path
    data = root / ".runtime" / "data"
    data.mkdir(parents=True)
    path = data / "games.sqlite"
    db = Database(path)
    db.initialize()
    for index in range(41):
        ingest_pgn(db, pgn(index, "Qg1" if index % 2 else "Qg7#"))
    ingest_pgn(db, pgn(40, "Qg7#", event="Duplicate import"))
    before = db.connection.total_changes
    monkeypatch.setattr(scan, "TURN_LIMIT", 4)
    monkeypatch.setattr(turns, "classify", lambda *args: ("missed", None))
    scan.run(db, "fixture_a", root)
    partial = cached_report(db, "fixture_a", root)
    assert partial["comparable"] and partial["newer"]["checked"] == 2
    assert partial["newer"]["unchecked"] == 18
    assert partial["earlier"]["checked"] == 2 and not partial["qualified"]
    for _ in range(9):
        scan.run(db, "fixture_a", root)
    completed = cached_report(db, "fixture_a", root)
    assert completed["newer"]["missed"] == completed["earlier"]["missed"] == 20
    assert completed["newer"]["complete"] and completed["earlier"]["complete"]
    assert completed["duplicates"] == 1 and completed["qualified"]
    assert db.connection.total_changes == before
    assert location(db, root).stat().st_mode & 0o777 == 0o600

    # A separate capture scan resumes fairly without changing the mate cache.
    from chess_coach import capture_game_trend_paths as capture_paths
    from chess_coach import capture_game_trend_scan as capture_scan
    from chess_coach.capture_game_trend_paths import binding as capture_binding
    from chess_coach.capture_game_trend_paths import location as capture_location
    from chess_coach.capture_game_trend_report import report as capture_report
    from chess_coach.capture_game_trend_validate import validate as capture_validate

    mate_before = read(location(db, root), binding(db, "fixture_a"))
    monkeypatch.setattr(
        capture_scan,
        "classify",
        lambda board, move, deadline, clock: ("played" if move.endswith("g7") else "other", None),
    )
    capture_scan.run(db, "fixture_a", root)
    capture_partial = capture_report(db, "fixture_a", root)
    assert capture_partial["comparable"] and not capture_partial["qualified"]
    assert capture_partial["newer"]["checked"] == capture_partial["earlier"]["checked"] == 2
    for _ in range(9):
        capture_scan.run(db, "fixture_a", root)
    capture_complete = capture_report(db, "fixture_a", root)
    assert capture_complete["qualified"] and capture_complete["duplicates"] == 1
    assert (
        capture_complete["newer"]["opportunities"]
        == capture_complete["earlier"]["opportunities"]
        == 20
    )
    assert capture_complete["newer"]["played"] == capture_complete["newer"]["other"] == 10
    assert read(location(db, root), binding(db, "fixture_a")) == mate_before
    capture_cache = capture_location(db, root)
    capture_state = read(
        capture_cache, capture_binding(db, "fixture_a"), validator=capture_validate
    )
    assert capture_state and capture_cache.stat().st_mode & 0o777 == 0o600
    assert read(capture_cache, capture_binding(db, "fixture_a")) is None
    assert read(capture_cache, capture_binding(db, "fixture_b"), validator=capture_validate) is None
    retained = capture_state["games"][0]
    source = turns.prepare(db, "fixture_a", retained["id"])
    kept = _item(source, retained["signature"], {str(retained["id"]): retained})
    assert kept["results"] == retained["results"]
    wrong = deepcopy(retained)
    wrong["results"][0][0] = 999999
    rejected = _item(source, retained["signature"], {str(retained["id"]): wrong})
    assert not rejected["results"]

    # A checksum is not enough: cache records must remain tied to their sources.
    for mutate in (
        lambda state: state["games"][0].update(id=999999),
        lambda state: state["games"][0].update(signature="wrong"),
        lambda state: state["games"][1].update(identity=state["games"][0]["identity"]),
        lambda state: state["games"][1]["results"][0].__setitem__(
            0, state["games"][0]["results"][0][0]
        ),
        lambda state: state.update(duplicates=state["duplicates"] + 1),
    ):
        corrupted = deepcopy(capture_state)
        mutate(corrupted)
        write(capture_cache, corrupted)
        assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["date"] = "1900-01-01T00:00:00+00:00"
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["results"][0][0] = 999999
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    corrupted = deepcopy(capture_state)
    corrupted["checked"].reverse()
    corrupted["games"].reverse()
    write(capture_cache, corrupted)
    assert capture_report(db, "fixture_a", root) is None
    capture_scan.run(db, "fixture_a", root)
    rebuilt = capture_report(db, "fixture_a", root)
    assert rebuilt and rebuilt["comparable"] and not rebuilt["qualified"]
    corrupted = deepcopy(capture_state)
    corrupted["games"][0]["eligible"] += 1
    corrupted["games"][0]["results"][0][0] = 999999
    corrupted["rotation"] = 0
    write(capture_cache, corrupted)
    capture_scan.run(db, "fixture_a", root)
    reset = read(capture_cache, capture_binding(db, "fixture_a"), validator=capture_validate)
    assert reset and not reset["checked"] and not reset["selection_complete"]
    write(capture_cache, capture_state)
    with monkeypatch.context() as patch:
        original_capture_binding = capture_binding(db, "fixture_a")
        patch.setattr(mate_paths, "PROOF_VERSION", "future-mate-policy")
        assert capture_binding(db, "fixture_a") == original_capture_binding
        assert binding(db, "fixture_a") != mate_before["binding"]
    with monkeypatch.context() as patch:
        patch.setattr(capture_paths, "PROOF_VERSION", "future-capture-policy")
        assert capture_report(db, "fixture_a", root) is None
    assert db.connection.total_changes == before

    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    client = app.test_client()
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.web_views.daily_plan", lambda *_args, **_kwargs: {})
        patch.setattr(
            "chess_coach.web_short_mate_game.capture_trend_report",
            lambda *_args: pytest.fail("Plan must not compute capture trend"),
        )
        plan = client.get(
            "/plan",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert plan.status_code == 200 and b"/game-samples/captures" in plan.data
    page = client.get(
        "/game-samples/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 200 and b"20 missed" in page.data
    assert b"100.0% earlier and 100.0% more recent" in page.data
    assert b"fixture_a" not in page.data and b"/decisions/" in page.data
    assert client.get("/game-samples/captures", base_url="https://coach.invalid").status_code == 403
    capture_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert (
        capture_page.status_code == 200
        and b"50.0% earlier and 50.0% more recent" in capture_page.data
    )
    assert b"/decisions/" in capture_page.data and b"/plan/captures" in capture_page.data
    assert (
        b"fixture_a" not in capture_page.data and b"not necessarily a mistake" in capture_page.data
    )
    original = capture_state["games"][0]["results"][0]
    capture_state["games"][0]["results"][0] = [
        original[0],
        "opportunity_unresolved",
        "played_capture_unresolved",
    ]
    write(capture_cache, capture_state)
    unresolved_capture = capture_report(db, "fixture_a", root)
    assert not unresolved_capture["qualified"]
    assert unresolved_capture["newer"]["opportunity_games"] == 20
    capture_page = client.get(
        "/game-samples/captures",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"A rate comparison is unavailable" in capture_page.data
    capture_state["games"][0]["results"][0] = original
    original_newer = [item["results"][0][:] for item in capture_state["games"][:20]]
    for item in capture_state["games"][:16]:
        item["results"][0] = [item["results"][0][0], "no_opportunity", None]
    write(capture_cache, capture_state)
    sparse_capture = capture_report(db, "fixture_a", root)
    assert sparse_capture["newer"]["complete"] and sparse_capture["newer"]["opportunities"] == 4
    assert not sparse_capture["qualified"]
    for item, old in zip(capture_state["games"][:20], original_newer, strict=True):
        item["results"][0] = old
    write(capture_cache, capture_state)
    cache = location(db, root)
    cached = read(cache, binding(db, "fixture_a"))
    old_result = cached["games"][0]["results"][0]
    cached["games"][0]["results"][0] = [old_result[0], "unknown", "node_limit"]
    write(cache, cached)
    unresolved = cached_report(db, "fixture_a", root)
    assert unresolved["newer"]["unknown"] == 1 and not unresolved["qualified"]
    page = client.get(
        "/game-samples/short-mate",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"A rate comparison is unavailable" in page.data
    cached["games"][0]["results"][0] = old_result
    write(cache, cached)
    assert cached_report(db, "fixture_b", root) is None

    duplicate = db.connection.execute(
        "SELECT id FROM games WHERE event='Duplicate import'"
    ).fetchone()["id"]
    position = db.connection.execute(
        "SELECT fen,san,uci FROM positions WHERE game_id=? LIMIT 1", (duplicate,)
    ).fetchone()
    db.connection.executemany(
        "INSERT INTO positions(game_id,ply,fen,san,uci) VALUES (?,?,?,?,?)",
        [(duplicate, ply, *position) for ply in range(10000, 11000)],
    )
    db.connection.commit()
    assert source_signature(db, {"id": duplicate}) == "oversized"
    assert cached_report(db, "fixture_a", root) is None
    assert capture_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    oversized = cached_report(db, "fixture_a", root)
    assert oversized and not oversized["comparable"] and oversized["unavailable"] == 1
    db.connection.execute("DELETE FROM positions WHERE game_id=? AND ply>=10000", (duplicate,))
    db.connection.commit()
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    assert cached_report(db, "fixture_a", root)["comparable"]

    db.connection.execute("UPDATE games SET result='0-1' WHERE id=?", (duplicate,))
    db.connection.commit()
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    changed = cached_report(db, "fixture_a", root)
    assert changed and not changed["comparable"] and changed["unavailable"] == 1
    import json

    cache = location(db, root)
    corrupt = json.loads(cache.read_text())
    corrupt["games"] = [{}]
    cache.write_text(json.dumps(corrupt))
    assert cached_report(db, "fixture_a", root) is None
    scan.run(db, "fixture_a", root)
    assert cached_report(db, "fixture_a", root) is not None
    cache.write_bytes(b"[" * 1500 + b"]" * 1500)
    assert cached_report(db, "fixture_a", root) is None
    cache.write_text("{invalid")
    assert cached_report(db, "fixture_a", root) is None
    db.close()
