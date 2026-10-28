"""Fetch or split a synchronization window without advancing its cursor."""

from __future__ import annotations

from .lichess_windows import Exporter, fetch_window, split_window


def validate_limits(max_games: int, page_size: int, since: int | None, now: int) -> int | None:
    if max_games < 1 or page_size < 1:
        raise ValueError("max_games and page_size must be positive")
    if since == 0:
        return None
    if since is not None and (since < 1356998401000 or since >= now * 1000):
        raise ValueError("since must be a supported past timestamp in milliseconds")
    return since


def fetch_step(
    client: Exporter, username: str, window: list[int], remaining: int, page_size: int
) -> tuple[list[str], list[list[int]] | None, int, bool]:
    limit = min(page_size, remaining, 999) + 1
    records = fetch_window(client, username, window, limit)
    if len(records) < limit:
        return records, None, 1, False
    children = split_window(window)
    if children is not None:
        return [], children, 1, False
    limit = min(remaining + 1, 1000)
    records = fetch_window(client, username, window, limit)
    return records, None, 2, len(records) >= limit
