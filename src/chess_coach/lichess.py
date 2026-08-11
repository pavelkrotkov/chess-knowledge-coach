"""Lichess PGN export and user-game synchronization."""

from __future__ import annotations

import io
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Protocol

import chess.pgn
import httpx

from .db import Database
from .ingest import ingest_pgn


class HttpClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


class LichessError(RuntimeError):
    """Raised when a Lichess export cannot be fetched after bounded retries."""


def _utc_millis(headers: chess.pgn.Headers) -> int | None:
    date = headers.get("UTCDate")
    clock = headers.get("UTCTime", "00:00:00")
    if not date:
        return None
    try:
        value = datetime.strptime(f"{date} {clock}", "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None
    return int(value.replace(tzinfo=UTC).timestamp() * 1000)


def _parse_games(payload: str) -> list[str]:
    games: list[str] = []
    stream = io.StringIO(payload)
    while game := chess.pgn.read_game(stream):
        games.append(str(game))
    return games


class LichessClient:
    """Small, bounded-retry client for the Lichess user export endpoint."""

    endpoint = "https://lichess.org/api/games/user/{username}"

    def __init__(
        self,
        token: str | None = None,
        *,
        client: HttpClient | None = None,
        retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.token = token
        self.client = client or httpx.Client(timeout=30.0)
        self.retries = max(0, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)

    def export_page(
        self,
        username: str,
        *,
        max_games: int = 100,
        since: int | None = None,
        until: int | None = None,
    ) -> list[str]:
        params: dict[str, int | str] = {
            "max": min(max(1000, max_games), 1000),
            "clocks": "true",
            "evals": "false",
            "opening": "true",
        }
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        headers = {"Accept": "application/x-chess-pgn"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = self.endpoint.format(username=username)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.get(url, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Lichess returned {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return _parse_games(response.text)
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
        raise LichessError(f"Unable to export games for {username}") from last_error

    def iter_user_games(
        self,
        username: str,
        *,
        max_games: int = 100,
        page_size: int = 100,
        since: int | None = None,
    ) -> Iterator[str]:
        """Yield at most ``max_games`` games, paging backwards by UTC timestamp."""
        remaining = max(0, max_games)
        until: int | None = None
        while remaining:
            page = self.export_page(
                username,
                max_games=min(page_size, remaining),
                since=since,
                until=until,
            )
            if not page:
                return
            yield from page[:remaining]
            remaining -= len(page)
            if len(page) < min(page_size, remaining + len(page)):
                return
            parsed = chess.pgn.read_game(io.StringIO(page[-1]))
            if parsed is None or (next_until := _utc_millis(parsed.headers)) is None:
                return
            until = next_until - 1

    def sync_user(
        self,
        db: Database,
        username: str,
        *,
        max_games: int = 100,
        page_size: int = 100,
        since: int | None = None,
    ) -> dict[str, int]:
        """Import exported games without persisting the optional API token."""
        totals = {"games": 0, "positions": 0}
        for raw_pgn in self.iter_user_games(
            username, max_games=max_games, page_size=page_size, since=since
        ):
            result = ingest_pgn(db, raw_pgn, source="lichess")
            totals = {key: totals[key] + result[key] for key in totals}
        return totals
