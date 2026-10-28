"""Lichess-compliant backoff for transient export failures."""

import httpx


def retry_delay(response: httpx.Response | None, attempt: int, backoff: float) -> float:
    if response is not None and response.status_code == 429:
        try:
            return max(60.0, float(response.headers.get("Retry-After", "60")))
        except ValueError:
            return 60.0
    return backoff * (2**attempt)
