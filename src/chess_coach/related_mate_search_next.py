"""Advance within a batch or to the next bounded corpus scan."""

from .related_capture_cursor import PAGE
from .related_mate_search_token import fingerprint, seen, within_limit


def advance(secret, state, chosen, keys):
    ordered = chosen[3]
    if state["offset"] + PAGE < len(ordered):
        return {
            **state,
            "offset": state["offset"] + PAGE,
            "scope": fingerprint(secret, "scope", chosen[4]),
        }, False
    if not any(keys):
        return None, False
    prompts, games = seen(secret, ordered)
    prompts = sorted(set(state["prompts"]) | set(prompts))
    games = sorted(set(state["games"]) | set(games))
    if not within_limit(prompts, games):
        return None, True
    return {
        **state,
        "keys": keys,
        "prompts": prompts,
        "games": games,
        "offset": 0,
        "scope": None,
    }, False
