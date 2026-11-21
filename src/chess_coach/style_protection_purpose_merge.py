"""Apply ordinary-first precedence independently for each protection dimension."""

from .style_protection_choices import NAMES
from .style_protection_guard import eligible as guard_eligible


def merge(key, item, ordinary, state):
    existing = ordinary.get(key)
    if existing is None:
        state["observations"].append(item)
        return
    replace = _replaceable(existing)
    if not replace:
        state["counts"]["protection_duplicate"] += 1
        return
    eligible = existing.get("eligible_dimensions", list(existing["choices"]))
    existing["eligible_dimensions"] = [name for name in eligible if name not in replace]
    item["eligible_dimensions"] = replace
    state["observations"].append(item)


def _replaceable(item):
    return [
        name for name in NAMES if not _supported(item, name) or item["choices"][name] == "ambiguous"
    ]


def _supported(item, name):
    if name == "protect_guard":
        return bool(item["pairs"]) and all(guard_eligible(pair) for pair in item["pairs"])
    return bool(item["pairs"]) and all(
        pair[side].get("protection", {}).get("status") == "supported"
        for pair in item["pairs"]
        for side in ("played", "alternative")
    )
