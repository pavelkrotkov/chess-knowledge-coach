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


class LichessSourceError(LichessError):
    """A sanitized HTTP or transport failure from the export source."""

    def __init__(self, message: str, reason: str, response=None):
        super().__init__(message)
        self.reason = reason
        self.response = response
        self.status = response.status_code if response is not None else None


def fetch_page(
    client: HttpClient,
    url: str,
    params: dict[str, int | str],
    headers: dict[str, str],
    retries: int,
    backoff: float,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[str]:
    # Preserve the last attempt's source classification without reporting a response
    # body or exception text. Retry timing still uses the actual response headers.
    failure = None
    for attempt in range(retries + 1):
        response = None
        try:
            response = _request(client, url, params, headers)
        except LichessSourceError as error:
            failure, response = error, error.response
            if _nonretryable(error):
                raise
        else:
            page = _parse(response)
            if page is not None:
                return page
            failure = None
        if attempt < retries:
            sleeper(retry_delay(response, attempt, backoff))
    if failure is not None:
        raise failure from None
    raise LichessError("Lichess export failed or was incomplete after retries")


def _request(client, url, params, headers):
    try:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as error:
        raise LichessSourceError(
            "Lichess rejected the export request", "source_http_error", error.response
        ) from None
    except httpx.RequestError:
        raise LichessSourceError(
            "Lichess export failed or was incomplete after retries", "source_transport_error"
        ) from None


def _parse(response):
    try:
        return parse_page(response.text)
    except ValueError:
        return None


def _nonretryable(error):
    return error.status is not None and error.status != 429 and error.status < 500
