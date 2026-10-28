"""Bounded nonpersistent iterator for callers of the original adapter."""

from __future__ import annotations

from collections.abc import Iterator

from .lichess_iterator_window import refetch_tied
from .lichess_support import supported
from .lichess_windows import Exporter, fetch_window, split_window


def iterate(
    client: Exporter, username: str, *, max_games: int, page_size: int, since: int | None, now: int
) -> Iterator[str]:
    windows = [[since // 1000 if since is not None else 0, now]]
    count = 0
    while windows and count < max_games:
        limit = min(max(1, page_size), max_games - count, 999) + 1
        records = fetch_window(client, username, windows[0], limit)
        if len(records) >= limit:
            children = split_window(windows[0])
            if children is None:
                eligible = refetch_tied(client, username, windows[0], max_games - count)
                yield from eligible
                count += len(eligible)
                windows.pop(0)
                continue
            windows[:1] = children
            continue
        windows.pop(0)
        for raw in records:
            if supported(raw):
                yield raw
                count += 1
