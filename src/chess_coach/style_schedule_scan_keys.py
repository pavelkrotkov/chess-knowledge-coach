"""Deduplicate replayed reserved games without changing ordinary scans."""

import hashlib


def identity(game, color, identities):
    key = identities.get(game["id"]) if identities is not None else None
    raw = hashlib.sha256((game["pgn"] + color).encode()).digest()
    return (key if key is not None else raw), key


def record(items, identities, seen, dedup, key):
    if identities is None:
        return
    for item in items:
        item["_game_key"] = key
    if key is not None:
        seen.add(dedup)


def mark_before(identities, key, seen, dedup):
    if identities is None or key is None:
        seen.add(dedup)
