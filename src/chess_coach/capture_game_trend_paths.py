"""Separate private cache and version binding for the capture proof."""

from .capture_game_proof import MAX_CANDIDATES
from .capture_game_proof import VERSION as PROOF_VERSION
from .fact_fingerprint import canonical, digest
from .material_capture_gain import MIN_GAIN
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES
from .material_reply_guard import MIN_GAIN as MIN_REPLY_GAIN
from .short_mate_trend_paths import location as game_location
from .short_mate_trend_paths import source_identity

VERSION = "capture-game-trend-v1"
TURN_SECONDS = 0.25


def location(db, root):
    path = game_location(db, root)
    return (
        path.with_name(path.name.removesuffix(".short-mate-trend.json") + ".capture-trend.json")
        if path
        else None
    )


def binding(db, learner):
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                source_identity(db, learner),
                MAX_CANDIDATES,
                MIN_GAIN,
                MAX_REPLIES,
                MIN_REPLY_GAIN,
                MAX_EXCHANGE_NODES,
                MAX_EXCHANGE_PLIES,
                TURN_SECONDS,
            ]
        )
    )
