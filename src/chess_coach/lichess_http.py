"""Bounded Lichess export requests with rate-limit aware retries."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

import httpx

from .lichess_parse import parse_page
from .lichess_retry import retry_delay


class HttpClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


class LichessError(RuntimeError):
    """Lichess export failed or returned incomplete data."""


def fetch_page(
    client: HttpClient,
    url: str,
    params: dict[str, int | str],
    headers: dict[str, str],
    retries: int,
    backoff: float,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[str]:
    for attempt in range(retries + 1):
        response = None
        try:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return parse_page(response.text)
        except httpx.HTTPStatusError as exc:
            response = exc.response
            if response.status_code != 429 and response.status_code < 500:
                raise LichessError("Lichess rejected the export request") from None
        except (httpx.RequestError, ValueError):
            pass
        if attempt < retries:
            sleeper(retry_delay(response, attempt, backoff))
    raise LichessError("Lichess export failed or was incomplete after retries")
