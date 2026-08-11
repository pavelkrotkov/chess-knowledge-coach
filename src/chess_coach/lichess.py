"""Lichess PGN export and user-game synchronization."""

from __future__ import annotations

import io
import re
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
    records = re.split(r"(?m)(?=^\[Event )", payload.strip())
    games: list[str] = []
    for record in records:
        if not record.strip():
            continue
        game = chess.pgn.read_game(io.StringIO(record))
        if game is not None:
            games.append(record.strip() + "\n")
    return games


def _headers(raw_pgn: str) -> chess.pgn.Headers | None:
    game = chess.pgn.read_game(io.StringIO(raw_pgn))
    return game.headers if game is not None else None


def _source_id(headers: chess.pgn.Headers) -> str:
    game_id = headers.get("GameId")
    if game_id:
        return game_id
    match = re.search(r"lichess\.org/([A-Za-z0-9]{6,})", headers.get("Site", ""))
    return match.group(1) if match else ""


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
            "max": min(max(1, max_games), 1000),
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
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    raise LichessError(f"Lichess rejected export for {username}") from exc
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
            except (httpx.RequestError, ValueError) as exc:
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
        page_size = min(1000, max(1, page_size))
        until: int | None = None
        seen_ids: set[str] = set()
        while remaining:
            request_size = min(page_size, remaining)
            page = self.export_page(
                username,
                max_games=request_size,
                since=since,
                until=until,
            )
            if not page:
                return
            yielded = 0
            newest_cursor: int | None = None
            for raw_pgn in page:
                headers = _headers(raw_pgn)
                if headers is None or headers.get("Variant", "Standard") != "Standard":
                    continue
                identifier = _source_id(headers) or raw_pgn
                cursor = _utc_millis(headers)
                if cursor is not None:
                    newest_cursor = cursor if newest_cursor is None else min(newest_cursor, cursor)
                if identifier in seen_ids:
                    continue
                seen_ids.add(identifier)
                yield raw_pgn
                yielded += 1
                remaining -= 1
                if not remaining:
                    return
            if len(page) < request_size or newest_cursor is None or yielded == 0:
                return
            # Lichess timestamps have one-second precision. Keep the boundary
            # inclusive and deduplicate to avoid silently skipping tied games.
            until = newest_cursor

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
            result = ingest_pgn(
                db,
                raw_pgn,
                source="lichess",
                raw_pgn_override=raw_pgn,
            )
            totals = {key: totals[key] + result[key] for key in totals}
        return totals
