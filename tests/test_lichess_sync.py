from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from chess_coach.db import Database
from chess_coach.lichess import LichessClient, LichessError
from chess_coach.lichess_parse import parse_page

NOW = 1_800_000_000


def game(game_id: str, created: int, *, variant: str = "Standard", result: str = "1-0") -> str:
    timestamp = datetime.fromtimestamp(created, UTC)
    return f"""[Event "Test"]
[Site "https://lichess.org/{game_id}"]
[GameId "{game_id}"]
[White "A"]
[Black "B"]
[UTCDate "{timestamp:%Y.%m.%d}"]
[UTCTime "{timestamp:%H:%M:%S}"]
[Variant "{variant}"]
[Result "{result}"]

1. e4 e5 {result}
"""


class Export:
    def __init__(self, entries: list[tuple[int, str]]) -> None:
        self.entries = entries
        self.calls = []
        self.fail_at = None

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append(kwargs)
        request = httpx.Request("GET", url)
        if self.fail_at == len(self.calls):
            raise httpx.ReadError("interrupted", request=request)
        params = kwargs["params"]
        assert isinstance(params, dict)
        since = params.get("since", 0)
        until = params.get("until", NOW * 1000 + 1000)
        selected = sorted(
            ((at, raw) for at, raw in self.entries if since <= at * 1000 < until),
            key=lambda row: row[0],
            reverse=True,
        )
        payload = "\n".join(raw for _, raw in selected[: params["max"]])
        return httpx.Response(200, text=payload, request=request)


def db_and_client(monkeypatch, entries):
    monkeypatch.setattr("chess_coach.lichess.time.time", lambda: NOW)
    db = Database(":memory:")
    db.initialize()
    service = Export(entries)
    return db, service, LichessClient(client=service, retries=0)


def advance(client, db, *, max_games=100, page_size=2, since=None, cycles=1):
    results = []
    for _ in range(100):
        result = client.sync_user(
            db, "learner", max_games=max_games, page_size=page_size, since=since
        )
        results.append(result)
        if result["history_cycles"] >= cycles and result["recent_complete"]:
            break
        if result["blocked_saturated"]:
            break
    return results


def test_multipage_bootstrap_ties_replay_and_counts(monkeypatch):
    entries = [
        (NOW - offset, game(f"game{offset:04}", NOW - offset)) for offset in (8, 8, 9, 10, 15)
    ]
    entries[1] = (NOW - 8, game("game000a", NOW - 8))
    db, service, client = db_and_client(monkeypatch, entries)
    results = advance(client, db, page_size=1, since=(NOW - 100) * 1000)
    assert results[-1]["bootstrap_complete"]
    assert not results[-1]["blocked_saturated"]
    assert sum(item["games"] for item in results) == 5
    assert sum(item["positions"] for item in results) == 10
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 5
    assert len(service.calls) > 2
    replay = advance(client, db, page_size=3, cycles=2)
    assert sum(item["games"] for item in replay) == 0
    assert sum(item["positions"] for item in replay) == 0


def test_interrupted_export_resumes_and_cursors_remain_durable(monkeypatch, tmp_path):
    entries = [
        (NOW - 10, game("fresh001", NOW - 10)),
        (NOW - 90_000, game("older001", NOW - 90_000)),
    ]
    monkeypatch.setattr("chess_coach.lichess.time.time", lambda: NOW)
    path = tmp_path / "sync.sqlite"
    db = Database(path)
    db.initialize()
    service = Export(entries)
    client = LichessClient(client=service, retries=0)
    first = client.sync_user(db, "learner", max_games=1, page_size=10)
    assert (first["games"], first["positions"]) == (1, 2)
    service.fail_at = len(service.calls) + 1
    with pytest.raises(LichessError, match="incomplete"):
        client.sync_user(db, "learner", max_games=10, page_size=10)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    db.close()
    db = Database(path)
    db.initialize()
    service.fail_at = None
    resumed = advance(client, db, page_size=10)
    assert sum(row["games"] for row in resumed) == 1
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


def test_historical_reconciliation_finds_game_finished_after_bootstrap(monkeypatch):
    entries = [(NOW - 99_000, game("old00001", NOW - 99_000))]
    db, service, client = db_and_client(monkeypatch, entries)
    first = advance(client, db, since=(NOW - 100_000) * 1000)
    assert first[-1]["bootstrap_complete"]
    service.entries.append((NOW - 90_000, game("late0001", NOW - 90_000)))
    later = advance(client, db, since=(NOW - 100_000) * 1000, cycles=2)
    assert sum(row["games"] for row in later) == 1
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


def test_unsplittable_tie_reports_incomplete_without_skipping(monkeypatch):
    entries = [(NOW - 1, game(f"tie{i:05}", NOW - 1)) for i in range(3)]
    db, _, client = db_and_client(monkeypatch, entries)
    results = advance(client, db, max_games=2, page_size=1, since=(NOW - 2) * 1000)
    assert results[-1]["blocked_saturated"]
    assert not results[-1]["bootstrap_complete"]
    assert not results[-1]["recent_complete"]
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_unsupported_is_counted_but_not_imported(monkeypatch):
    entries = [(NOW - 1, game("variant1", NOW - 1, variant="Chess960"))]
    db, _, client = db_and_client(monkeypatch, entries)
    result = client.sync_user(db, "learner", max_games=10, page_size=10)
    assert result["unsupported"] >= 1
    assert result["games"] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_malformed_truncated_and_invalid_move_text_fail_closed():
    pgn = game("valid001", NOW - 1)
    for invalid in (pgn.removesuffix("1-0\n"), pgn.replace("e4 e5", "e4 Qh9")):
        with pytest.raises(ValueError):
            parse_page(invalid)


def test_429_waits_at_least_one_minute_before_bounded_retry():
    class RateLimited:
        def __init__(self):
            self.calls = 0

        def get(self, url, **kwargs):
            self.calls += 1
            request = httpx.Request("GET", url)
            if self.calls == 1:
                return httpx.Response(429, headers={"Retry-After": "5"}, request=request)
            return httpx.Response(200, text=game("valid001", NOW - 1), request=request)

    delays = []
    service = RateLimited()
    client = LichessClient(client=service, retries=1, sleeper=delays.append)
    assert len(client.export_page("learner")) == 1
    assert delays == [60.0]


def test_conflicting_replay_preserves_raw_game_and_window(monkeypatch):
    entry = game("stable01", NOW - 1)
    db, service, client = db_and_client(monkeypatch, [(NOW - 1, entry)])
    assert advance(client, db)[-1]["bootstrap_complete"]
    before = db.connection.execute("SELECT pgn FROM games").fetchone()[0]
    service.entries = [(NOW - 1, entry.replace("e4 e5", "d4 d5"))]
    with pytest.raises(ValueError, match="conflicting PGN"):
        client.sync_user(db, "learner", max_games=10, page_size=10)
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == before
    assert db.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 2


def test_window_import_failure_rolls_back_all_games_and_resumes(monkeypatch):
    from chess_coach import lichess_import

    entries = [(NOW - 1, game("first001", NOW - 1)), (NOW - 2, game("next0001", NOW - 2))]
    db, _, client = db_and_client(monkeypatch, entries)
    original = lichess_import.ingest_in_transaction
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("injected")
        return original(*args, **kwargs)

    monkeypatch.setattr(lichess_import, "ingest_in_transaction", fail_on_second)
    with pytest.raises(RuntimeError, match="injected"):
        client.sync_user(db, "learner", max_games=10, page_size=10)
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    monkeypatch.setattr(lichess_import, "ingest_in_transaction", original)
    assert advance(client, db, page_size=10)[-1]["bootstrap_complete"]
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


def test_invalid_game_does_not_log_player_headers(caplog):
    invalid = game("invalid1", NOW - 1).replace('[White "A"]', '[White "Sample Player"]')
    invalid = invalid.replace("1. e4 e5", "1. e4 e5 2. Ke3")
    with pytest.raises(ValueError, match="invalid"):
        parse_page(invalid)
    assert "Sample Player" not in caplog.text


def test_progress_conflict_rolls_back_imported_window(monkeypatch):
    from chess_coach.lichess_commit import apply_window
    from chess_coach.lichess_progress import prepare_progress

    db, _, _ = db_and_client(monkeypatch, [])
    state = prepare_progress(db, "learner", None, NOW + 1)
    db.connection.execute("UPDATE sync_progress SET revision = revision + 1")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="concurrently"):
        apply_window(db, state, "recent_windows", [game("race0001", NOW - 1)])
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_v2_upgrade_preserves_games_and_adds_sync_progress():
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('existing', 'A', 'B', '*')"
    )
    db.connection.execute("DROP TABLE sync_progress")
    db.connection.execute("PRAGMA user_version = 2")
    db.connection.commit()
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == "existing"
    assert db.connection.execute("SELECT COUNT(*) FROM sync_progress").fetchone()[0] == 0
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_rate_limit_retries_are_bounded_and_keep_progress(monkeypatch):
    class AlwaysLimited:
        def __init__(self):
            self.calls = 0

        def get(self, url, **kwargs):
            self.calls += 1
            return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr("chess_coach.lichess.time.time", lambda: NOW)
    db = Database(":memory:")
    db.initialize()
    delays = []
    service = AlwaysLimited()
    client = LichessClient(client=service, retries=2, sleeper=delays.append)
    with pytest.raises(LichessError, match="after retries"):
        client.sync_user(db, "learner")
    assert service.calls == 3
    assert delays == [60.0, 60.0]
    assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    assert db.connection.execute("SELECT history_cycles FROM sync_progress").fetchone()[0] == 0


def test_zero_since_retains_account_start_compatibility(monkeypatch):
    db, _, client = db_and_client(monkeypatch, [(NOW - 1, game("compat01", NOW - 1))])
    result = client.sync_user(db, "learner", since=0)
    assert result["games"] == 1
    assert db.connection.execute("SELECT history_start FROM sync_progress").fetchone()[0] == 0
