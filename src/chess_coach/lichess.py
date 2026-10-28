"""Lichess export client and restartable account synchronization."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import cast

import httpx

from .db import Database
from .lichess_http import HttpClient, fetch_page
from .lichess_http import LichessError as LichessError
from .lichess_iterator import iterate
from .lichess_sync import sync


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
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.token = token
        self.client: HttpClient = client or cast(HttpClient, httpx.Client(timeout=30.0))
        self.retries = max(0, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.sleeper = sleeper

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
            "ongoing": "false",
            "finished": "true",
        }
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until
        headers = {"Accept": "application/x-chess-pgn"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return fetch_page(
            self.client,
            self.endpoint.format(username=username),
            params,
            headers,
            self.retries,
            self.backoff_seconds,
            self.sleeper,
        )

    def iter_user_games(
        self,
        username: str,
        *,
        max_games: int = 100,
        page_size: int = 100,
        since: int | None = None,
    ) -> Iterator[str]:
        yield from iterate(
            self,
            username,
            max_games=max_games,
            page_size=page_size,
            since=since,
            now=int(time.time()) + 1,
        )

    def sync_user(
        self,
        db: Database,
        username: str,
        *,
        max_games: int = 100,
        page_size: int = 100,
        since: int | None = None,
    ) -> dict:
        """Import bounded windows and persist separate recent and history progress."""
        return sync(
            self,
            db,
            username,
            max_games=max_games,
            page_size=page_size,
            since=since,
            now=int(time.time()) + 1,
        )
