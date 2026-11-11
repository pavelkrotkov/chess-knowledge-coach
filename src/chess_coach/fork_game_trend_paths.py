"""Bind a private game scan to the knight-fork proof policy and learner."""

from .fact_fingerprint import canonical, digest
from .fork_contract import VERSION as FORK_VERSION
from .fork_game_proof import VERSION as PROOF_VERSION
from .fork_proof import MAX_REPLIES
from .material_capture_gain import MIN_GAIN
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES as CAPTURE_REPLIES
from .material_reply_guard import MIN_GAIN as MIN_REPLY_GAIN
from .material_values import VALUES
from .short_mate_trend_paths import location as game_location
from .short_mate_trend_paths import source_identity

VERSION = "knight-fork-game-trend-v1"
TURN_SECONDS = 0.25


def location(db, root):
    path = game_location(db, root)
    return (
        path.with_name(path.name.removesuffix(".short-mate-trend.json") + ".knight-fork-trend.json")
        if path
        else None
    )


def binding(db, learner):
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                FORK_VERSION,
                source_identity(db, learner),
                MAX_REPLIES,
                MIN_GAIN,
                MIN_REPLY_GAIN,
                sorted(VALUES.items()),
                MAX_EXCHANGE_NODES,
                MAX_EXCHANGE_PLIES,
                CAPTURE_REPLIES,
                TURN_SECONDS,
            ]
        )
    )
