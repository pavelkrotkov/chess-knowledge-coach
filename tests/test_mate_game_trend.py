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

    # The fork scan uses its own bounded sidecar and dated cohorts.
    from chess_coach.fork_game_trend_report import report as fork_report
    from chess_coach.fork_game_trend_scan import run as run_forks

    with monkeypatch.context() as patch:
        patch.setattr(scan, "TURN_LIMIT", 40)
        run_forks(db, "fixture_a", root)
    fork_cohorts = fork_report(db, "fixture_a", root)
    assert fork_cohorts and fork_cohorts["selection_complete"]
    assert fork_cohorts["newer"]["games"] == fork_cohorts["earlier"]["games"] == 20
    assert fork_cohorts["newer"]["oldest"] > fork_cohorts["earlier"]["newest"]
    assert fork_cohorts["newer"]["opportunities"] == fork_cohorts["earlier"]["opportunities"] == 0
    assert fork_cohorts["newer"]["no_candidate"] == fork_cohorts["earlier"]["no_candidate"] == 20
    assert db.connection.total_changes == before

    # A separate capture scan resumes fairly without changing the mate cache.
    from chess_coach import capture_game_trend_paths as capture_paths
    from chess_coach import capture_game_trend_scan as capture_scan
    from chess_coach.capture_game_trend_paths import binding as capture_binding
    from chess_coach.capture_game_trend_paths import location as capture_location
    from chess_coach.capture_game_trend_report import report as capture_report
    from chess_coach.capture_game_trend_validate import validate as capture_validate

    mate_before = read(location(db, root), binding(db, "fixture_a"))
    # The new policy starts a distinct sidecar and keeps the earlier history.
    capture_cache = capture_location(db, root)
    assert capture_cache.name.endswith(".capture-trend-v2.json")
    old_capture_cache = capture_cache.with_name(
        capture_cache.name.replace(".capture-trend-v2.json", ".capture-trend.json")
    )
    old_capture_cache.write_bytes(b"synthetic prior capture cache")
    old_capture_cache.chmod(0o600)
    monkeypatch.setattr(
        capture_scan,
        "classify",
        lambda board, move, deadline, clock: ("played" if move.endswith("g7") else "other", None),
    )
    capture_scan.run(db, "fixture_a", root)
    assert old_capture_cache.read_bytes() == b"synthetic prior capture cache"
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
    assert old_capture_cache.read_bytes() == b"synthetic prior capture cache"
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
    fork_empty = client.get(
        "/game-samples/knight-forks",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert fork_empty.status_code == 200 and b"0 turns had a proved fork" in fork_empty.data
    assert b"Rates require" in fork_empty.data and b"0.0%" not in fork_empty.data
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

    # Real worker-to-browser readiness: proved played, proved alternative,
    # and a geometric fork whose bounded proof cannot qualify it.
    import chess.engine

    from chess_coach import fork_game_proof, fork_game_trend_paths

    fork_path = data / "fork-games.sqlite"
    fork_db = Database(fork_path)
    fork_db.initialize()
    supported = "b3k3/4B3/5K1p/1N3b2/8/8/8/8 w - - 0 2"
    unproved = "b3k3/4B3/5K1p/1N3b2/8/8/8/r7 w - - 0 2"
    for index, (fen, move) in enumerate(
        ((supported, "Nc7+"), (supported, "Kg7"), (unproved, "Kg7")), 1
    ):
        ingest_pgn(fork_db, pgn(index, move).replace(FEN, fen))
    changes = fork_db.connection.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(scan, "TURN_LIMIT", 1)
        run_forks(fork_db, "fixture_a", root)
        pending = fork_report(fork_db, "fixture_a", root)
        assert pending and pending["newer"]["scanned"] == 1
        assert pending["newer"]["unchecked"] == 2
        assert pending["newer"]["opportunities"] == 0 and pending["newer"]["unresolved"] == 1
        for _ in range(2):
            run_forks(fork_db, "fixture_a", root)
    fork_result = fork_report(fork_db, "fixture_a", root)
    assert fork_result and fork_result["selection_complete"]
    newer, earlier = fork_result["newer"], fork_result["earlier"]
    assert (newer["games"], newer["eligible"], newer["scanned"]) == (3, 3, 3)
    assert (newer["opportunities"], newer["played"], newer["awaiting"]) == (2, 1, 1)
    assert newer["unresolved"] == newer["unresolved_roots"] == 1
    assert earlier["games"] == 0 and newer["unchecked"] == 0
    assert newer["examples"][0]["outcome"] in {"played", "awaiting"}
    assert fork_game_trend_paths.location(fork_db, root).stat().st_mode & 0o777 == 0o600
    assert fork_db.connection.total_changes == changes

    fork_app = create_app(
        db_path=fork_path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    fork_client = fork_app.test_client()
    fork_headers = {"Tailscale-User-Login": "fixture"}
    fork_url = "/game-samples/knight-forks"
    assert fork_client.get(fork_url, base_url="https://coach.invalid").status_code == 403
    version = fork_db.connection.execute("PRAGMA data_version").fetchone()[0]
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_game_proof, "fork_proof", lambda *_args, **_kwargs: pytest.fail("browser proof")
        )
        patch.setattr(
            chess.engine.SimpleEngine, "popen_uci", lambda *_args, **_kwargs: pytest.fail("engine")
        )
        page = fork_client.get(fork_url, base_url="https://coach.invalid", headers=fork_headers)
        plan = fork_client.get("/plan", base_url="https://coach.invalid", headers=fork_headers)
    assert page.status_code == 200 and b"3 of 3 learner turns attempted" in page.data
    assert b"2 turns had a proved fork" in page.data and b"1 await comparison" in page.data
    assert b"1 turns had at least one unproved" in page.data
    assert b"/decisions/" in page.data and b"Rates require" in page.data
    assert b"fixture_a" not in page.data and b"fixture_b" not in page.data
    assert b"/game-samples/knight-forks" in plan.data
    assert fork_db.connection.execute("PRAGMA data_version").fetchone()[0] == version
    assert fork_db.connection.total_changes == changes

    from chess_coach.fork_game_trend_validate import validate as fork_validate

    fork_cache = fork_game_trend_paths.location(fork_db, root)
    fork_binding = fork_game_trend_paths.binding(fork_db, "fixture_a")
    fork_state = read(fork_cache, fork_binding, validator=fork_validate)
    assert fork_state and read(fork_cache, fork_binding) is None
    malformed = deepcopy(fork_state)
    unresolved = next(
        row for game in malformed["games"] for row in game["results"] if row[1] == "unresolved"
    )
    unresolved[2] = None
    write(fork_cache, malformed)
    assert fork_report(fork_db, "fixture_a", root) is None
    write(fork_cache, fork_state)

    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "PROOF_VERSION", "changed-proof")
        assert fork_report(fork_db, "fixture_a", root) is None
    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "VALUES", {1: 2})
        assert fork_report(fork_db, "fixture_a", root) is None

    # Exercise the real classifier deadline through the shared worker and sidecar.
    from chess_coach import fork_game_trend_scan

    with monkeypatch.context() as patch:
        patch.setattr(fork_game_trend_paths, "PROOF_VERSION", "deadline-fixture")
        patch.setattr(scan, "TURN_LIMIT", 1)
        patch.setattr(
            fork_game_trend_scan,
            "classify",
            lambda board, played, deadline, clock: fork_game_proof.classify(
                board, played, deadline, lambda: deadline
            ),
        )
        run_forks(fork_db, "fixture_a", root)
        deadline_state = read(
            fork_cache, fork_game_trend_paths.binding(fork_db, "fixture_a"), validator=fork_validate
        )
        assert deadline_state
        assert [row[1:] for game in deadline_state["games"] for row in game["results"]] == [
            ["unknown", "turn_deadline"]
        ]
    write(fork_cache, fork_state)
    fork_db.connection.execute("UPDATE games SET result='0-1' WHERE id=1")
    fork_db.connection.commit()
    assert fork_report(fork_db, "fixture_a", root) is None
    stale = fork_client.get(fork_url, base_url="https://coach.invalid", headers=fork_headers)
    assert b"scan is pending or its sources changed" in stale.data
    fork_db.close()

    # A full, independent synthetic sample with current same-source analysis.
    import sys

    from chess_coach import fork_miss_candidate, fork_miss_worker
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_fork_pipeline import Engine

    matched_path = data / "matched-forks.sqlite"
    matched = Database(matched_path)
    matched.initialize()
    fen = "r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1"
    for index in range(41):
        position = fen if index != 1 else "r3k3/7p/8/1N6/8/8/6P1/r6K w - - 0 1"
        move = "Kh2" if index == 1 else ("Kg1" if index % 2 else "Nc7+")
        game = pgn(index, move).replace(FEN, position)
        ingest_pgn(matched, game.replace('[Result "1-0"]', '[TimeControl "600+0"]\n[Result "1-0"]'))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_a", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    engine_hash = engine_identity(sys.executable)
    for game_id in (1, *range(4, 42)):
        assert (
            run_analysis(matched, game_id, game_input(matched, game_id), config, engine_hash)[
                "status"
            ]
            == "complete"
        )
    for _ in range(30):
        run_forks(matched, "fixture_a", root)
        current = fork_report(matched, "fixture_a", root)
        if current and current["newer"]["unchecked"] == current["earlier"]["unchecked"] == 0:
            break
    else:
        pytest.fail("readiness scan did not finish")
    for _ in range(15):
        fork_miss_worker.run(matched, "fixture_a", root)
        current = fork_report(matched, "fixture_a", root)
        if (
            current
            and current["comparison"]
            and not (
                current["comparison"]["newer"]["pending"]
                + current["comparison"]["earlier"]["pending"]
            )
        ):
            break
    assert current["comparison"] and not current["comparison"]["qualified"]
    assert current["comparison"]["earlier"]["unresolved"] == 1
    assert (
        run_analysis(matched, 3, game_input(matched, 3), config, engine_hash)["status"]
        == "complete"
    )
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    fork_miss_worker.run(matched, "fixture_a", root)
    current = fork_report(matched, "fixture_a", root)
    assert current["comparison"]["qualified"]
    assert current["comparison"]["newer"]["miss"] == 10
    assert current["comparison"]["earlier"]["miss"] == 9
    assert current["newer"]["unknown"] == 0 and current["earlier"]["unknown"] == 1
    assert (
        current["comparison"]["newer"]["played"] == current["comparison"]["earlier"]["played"] == 10
    )
    app = create_app(
        db_path=matched_path,
        subject="fixture_a",
        actor="operator",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
        project_root=root,
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_miss_candidate, "fork_proof", lambda *_args, **_kw: pytest.fail("browser proof")
        )
        patch.setattr(
            chess.engine.SimpleEngine, "popen_uci", lambda *_args: pytest.fail("browser engine")
        )
        page = app.test_client().get(
            "/game-samples/knight-forks",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
    assert b"50.0% across 20 resolved opportunities" in page.data
    assert b"47.4% across 19 resolved opportunities" in page.data

    # A different known time control blocks comparison even for an unsupported turn.
    from chess_coach.fork_miss_time import _times

    matched.connection.execute("UPDATE games SET time_control='0+3' WHERE id=2")
    matched.connection.commit()
    assert _times(matched, [{"id": 2}])["0+3"] == 1
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    matched.connection.execute("UPDATE games SET time_control='0+0' WHERE id=2")
    assert _times(matched, [{"id": 2}]) is None
    matched.connection.execute("UPDATE games SET time_control='600+0' WHERE id=2")
    matched.connection.commit()

    # A proof timeout remains pending, then the worker resumes that exact turn.
    from chess_coach.fork_game_proof import Deadline
    from chess_coach.fork_miss_store import binding as miss_binding
    from chess_coach.fork_miss_store import location as miss_location
    from chess_coach.fork_miss_store import validate as miss_validate

    miss_cache = miss_location(matched, root)
    miss_key = miss_binding(matched, "fixture_a")
    miss_state = read(miss_cache, miss_key, validator=miss_validate)
    position = next(key for key, row in miss_state["rows"].items() if row[2] == "miss")
    miss_state["rows"][position][2] = "retry"
    write(miss_cache, miss_state)
    with monkeypatch.context() as patch:

        def expire(*args, **kwargs):
            raise Deadline()

        patch.setattr(fork_miss_candidate, "fork_proof", expire)
        fork_miss_worker.run(matched, "fixture_a", root)
    timed = fork_report(matched, "fixture_a", root)["comparison"]
    assert not timed["qualified"] and timed["newer"]["pending"] + timed["earlier"]["pending"] == 1
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Late per-entry expiry retries, and a cycle timeout preserves prior entries.
    import sqlite3
    import time
    from contextlib import contextmanager

    from chess_coach import fork_miss_entry, fork_miss_progress
    from chess_coach.opening_queue_budget import BrowserBudget
    from chess_coach.tactical_course_budget import PreviewUnavailable

    late = {"expired": False}
    original_config = fork_miss_entry.configuration
    original_check = fork_miss_entry._check

    def late_config(*args):
        result = original_config(*args)
        late["expired"] = True
        return result

    def late_check(deadline):
        if late["expired"]:
            raise Deadline()
        original_check(deadline)

    with monkeypatch.context() as patch:
        patch.setattr(fork_miss_entry, "configuration", late_config)
        patch.setattr(fork_miss_entry, "_check", late_check)
        retry = fork_miss_entry._entry(
            matched,
            "fixture_a",
            miss_state["rows"][position][0],
            int(position),
            "awaiting",
            time.monotonic() + 10,
        )
        assert retry[2] == "retry"

    readiness_cache = fork_game_trend_paths.location(matched, root)
    readiness_key = fork_game_trend_paths.binding(matched, "fixture_a")
    full = read(readiness_cache, readiness_key, validator=fork_validate)
    entries = fork_miss_progress._entries(full)
    first, second = (str(entry[1]) for entry in entries[:2])
    paused = read(miss_cache, miss_key, validator=miss_validate)
    first_result = paused["rows"][first][2]
    paused["rows"][first][2] = paused["rows"][second][2] = "retry"
    paused["rotation"] = 0
    write(miss_cache, paused)
    original_step = fork_miss_progress._step
    steps = []

    original_scope = BrowserBudget.scope

    @contextmanager
    def stop_second(self, *, snapshot):
        with original_scope(self, snapshot=snapshot):
            yield
            steps.append(1)
            if len(steps) == 2:
                raise PreviewUnavailable("synthetic timeout after guarded work")

    with monkeypatch.context() as patch:
        patch.setattr(BrowserBudget, "scope", stop_second)
        fork_miss_worker.run(matched, "fixture_a", root)
    resumed = read(miss_cache, miss_key, validator=miss_validate)
    assert resumed["rows"][first][2] == first_result and resumed["rows"][second][2] == "retry"
    assert resumed["rotation"] == 2
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Do not publish the completed prefix if another connection changes the data.
    write(miss_cache, paused)
    steps.clear()
    other = sqlite3.connect(matched_path)

    def change_second(*args):
        steps.append(1)
        if len(steps) == 2:
            other.execute("UPDATE analysis_runs SET engine_version='temporary' WHERE game_id=3")
            other.commit()
            raise PreviewUnavailable("synthetic source change")
        return original_step(*args)

    with monkeypatch.context() as patch:
        patch.setattr(fork_miss_progress, "_step", change_second)
        fork_miss_worker.run(matched, "fixture_a", root)
    assert read(miss_cache, miss_key, validator=miss_validate) == paused
    other.execute("UPDATE analysis_runs SET engine_version='synthetic' WHERE game_id=3")
    other.commit()
    other.close()
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Retain exact earlier opportunities when the readiness prefix grows.
    readiness_cache = fork_game_trend_paths.location(matched, root)
    readiness_key = fork_game_trend_paths.binding(matched, "fixture_a")
    full = read(readiness_cache, readiness_key, validator=fork_validate)
    partial = deepcopy(full)
    game = next(game for game in partial["games"] if game["results"][0][1] == "awaiting")
    game["results"].pop()
    write(readiness_cache, partial)
    fork_miss_worker.run(matched, "fixture_a", root)
    retained = read(miss_cache, miss_key, validator=miss_validate)["rows"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    grown = read(miss_cache, miss_key, validator=miss_validate)["rows"]
    assert all(grown[key] == row for key, row in retained.items())
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # Unproved turns can change the order, so overlapping bounds withhold rates.
    uncertain_state = deepcopy(full)
    unknown = next(
        row
        for game in uncertain_state["games"]
        for row in game["results"]
        if row[1:] == ["unknown", "unsupported_position"]
    )
    unknown[1:] = ["unresolved", "unresolved_roots"]
    write(readiness_cache, uncertain_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    uncertain = fork_report(matched, "fixture_a", root)["comparison"]
    assert uncertain["earlier"]["uncertain"] == 1 and not uncertain["qualified"]
    hidden = app.test_client().get(
        "/game-samples/knight-forks",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert b"additional turns had unproved fork candidates" in hidden.data
    assert b"verified miss rate was" not in hidden.data
    from chess_coach.fork_miss_bounds import separated

    assert separated(
        [
            {"opportunities": 5, "miss": 0, "uncertain": 1},
            {"opportunities": 10, "miss": 10, "uncertain": 0},
        ]
    )

    # Other unproved roots on an already proved turn are not extra opportunities.
    proved_state = deepcopy(full)
    played = next(
        row for game in proved_state["games"] for row in game["results"] if row[1] == "played"
    )
    played[2] = "unresolved_roots"
    write(readiness_cache, proved_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    proved = fork_report(matched, "fixture_a", root)["comparison"]
    assert proved["newer"]["uncertain"] == proved["earlier"]["uncertain"] == 0
    assert proved["qualified"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A readiness proof timeout blocks rates, unlike known unsupported coverage.
    timeout_state = deepcopy(full)
    unknown = next(
        row
        for game in timeout_state["games"]
        for row in game["results"]
        if row[1:] == ["unknown", "unsupported_position"]
    )
    unknown[2] = "turn_deadline"
    write(readiness_cache, timeout_state)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    write(readiness_cache, full)
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A valid checksum cannot turn an awaiting result into a played result.
    stable = read(miss_cache, miss_key, validator=miss_validate)
    forged = deepcopy(stable)
    miss_position = next(key for key, row in forged["rows"].items() if row[2] == "miss")
    forged["rows"][miss_position][2] = "played"
    write(miss_cache, forged)
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    write(miss_cache, stable)

    # Changed engine identity invalidates the source and blocks matched analysis.
    matched.connection.execute(
        "UPDATE analysis_runs SET engine_version='different synthetic engine' WHERE game_id=3"
    )
    matched.connection.commit()
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    fork_miss_worker.run(matched, "fixture_a", root)
    assert not fork_report(matched, "fixture_a", root)["comparison"]["qualified"]
    matched.connection.execute(
        "UPDATE analysis_runs SET engine_version='synthetic' WHERE game_id=3"
    )
    matched.connection.commit()
    fork_miss_worker.run(matched, "fixture_a", root)
    assert fork_report(matched, "fixture_a", root)["comparison"]["qualified"]

    # A geometric played knight root may be an unresolved equivalent.
    board = chess.Board(fen)
    with monkeypatch.context() as patch:
        patch.setattr(
            fork_miss_candidate, "fork_proof", lambda *_args, **_kw: pytest.fail("unexpected proof")
        )
        assert (
            fork_miss_candidate.candidate(
                board, chess.Move.from_uci("b5c7"), chess.Move.from_uci("b5d6"), {}, lambda: None
            )
            == "unresolved"
        )

    matched.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=3 AND role='best'"
    )
    matched.connection.commit()
    assert fork_report(matched, "fixture_a", root)["comparison"] is None
    matched.close()
