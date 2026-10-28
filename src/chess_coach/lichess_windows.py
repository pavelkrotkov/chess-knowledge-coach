"""Bounded half-open creation-time windows for Lichess exports."""

from __future__ import annotations

from typing import Protocol

API_MIN_SECOND = 1356998401


class Exporter(Protocol):
    def export_page(
        self,
        username: str,
        *,
        max_games: int = 100,
        since: int | None = None,
        until: int | None = None,
    ) -> list[str]: ...


def fetch_window(client: Exporter, username: str, window: list[int], limit: int) -> list[str]:
    start, end = window
    since = start * 1000 if start else None
    return client.export_page(username, max_games=limit, since=since, until=end * 1000)


def split_window(window: list[int]) -> list[list[int]] | None:
    start, end = window
    midpoint = (start + end) // 2
    if start == 0:
        midpoint = max(midpoint, API_MIN_SECOND)
    if midpoint <= start or midpoint >= end:
        return None
    return [[midpoint, end], [start, midpoint]]


def choose_field(state: dict, index: int) -> str | None:
    fields = (
        ("recent_windows", "history_windows")
        if index % 2 == 0
        else ("history_windows", "recent_windows")
    )
    return next((field for field in fields if state[field]), None)
