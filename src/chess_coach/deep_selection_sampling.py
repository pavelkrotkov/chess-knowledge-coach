"""Pick reproducible control positions from a stable game identity."""

from .deep_selection_categories import categories
from .fact_fingerprint import canonical, digest

CONTROL_POLICY_VERSION = "controls-v1"


def sample_key(game_key, item):
    return digest(
        canonical(
            {
                "game": game_key,
                "ply": item["ply"],
                "fen": item["fen"],
                "policy": CONTROL_POLICY_VERSION,
            }
        )
    )


def controls(ordered, limit):
    if not limit:
        return []
    target = min(len(ordered), (limit + 3) // 4)
    ordinary = [item for item in ordered if not categories(item["reasons"])]
    fallback = [item for item in ordered if categories(item["reasons"])]
    return (ordinary + fallback)[:target]
