"""Stable ranking independent of engine scores and game outcomes."""

import hashlib


def rank(key, kind, game_id, position_id):
    value = f"{key}:{kind}:{game_id}:{position_id}"
    return hashlib.sha256(value.encode()).hexdigest()
