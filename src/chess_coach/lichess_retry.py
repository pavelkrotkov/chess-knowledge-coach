"""Lichess-compliant backoff for transient export failures."""

from __future__ import annotations

import math
import time
from datetime import UTC
from email.utils import parsedate_to_datetime

import httpx


def header_delay(value: str | None, now: float) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            seconds = date.timestamp() - now
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def retry_delay(
    response: httpx.Response | None, attempt: int, backoff: float, *, now: float | None = None
) -> float:
    delay = backoff * (2**attempt)
    if response is None:
        return delay
    requested = header_delay(
        response.headers.get("Retry-After"), time.time() if now is None else now
    )
    if requested is not None:
        delay = max(delay, requested)
    if response.status_code == 429:
        delay = max(delay, 60.0)
    return delay
