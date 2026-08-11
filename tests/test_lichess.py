from __future__ import annotations

import httpx

from chess_coach.db import Database
from chess_coach.lichess import LichessClient

PGN = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abc123"]
[Date "2026.08.11"]
[Round "-"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[GameId "abc123"]
[UTCDate "2026.08.11"]
[UTCTime "12:00:00"]
[Variant "Standard"]
[TimeControl "180+2"]
[WhiteElo "1500"]
[BlackElo "1490"]
[Termination "Time forfeit"]

1. e4 {[%clk 0:03:00]} e5 2. Nf3 1-0
"""


class FakeClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return httpx.Response(200, text=self.payload, request=httpx.Request("GET", url))


def test_sync_preserves_lichess_metadata_and_is_idempotent() -> None:
    db = Database(":memory:")
    db.initialize()
    fake = FakeClient(PGN)
    client = LichessClient(client=fake)

    assert client.sync_user(db, "alice", max_games=1) == {"games": 1, "positions": 3}
    assert client.sync_user(db, "alice", max_games=1) == {"games": 1, "positions": 3}
    game = db.connection.execute(
        "SELECT source, source_id, variant, termination, time_control, white_elo FROM games"
    ).fetchone()
    assert tuple(game) == ("lichess", "abc123", "Standard", "Time forfeit", "180+2", 1500)
    assert len(fake.calls) == 2


def test_token_is_sent_only_as_http_header() -> None:
    fake = FakeClient(PGN)
    client = LichessClient(token="secret", client=fake)

    client.export_page("alice", max_games=1)

    request = fake.calls[0]
    assert request["headers"] == {
        "Accept": "application/x-chess-pgn",
        "Authorization": "Bearer secret",
    }
    assert "secret" not in str(request["params"])
