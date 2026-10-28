"""Resolve one-second ties for the bounded nonpersistent iterator."""

from .lichess_http import LichessError
from .lichess_support import supported
from .lichess_windows import Exporter, fetch_window


def refetch_tied(client: Exporter, username: str, window: list[int], remaining: int) -> list[str]:
    records = fetch_window(client, username, window, 1000)
    eligible = [raw for raw in records if supported(raw)]
    if len(records) == 1000 and len(eligible) < remaining:
        raise LichessError("saturated export window cannot be fully enumerated")
    return eligible[:remaining]
