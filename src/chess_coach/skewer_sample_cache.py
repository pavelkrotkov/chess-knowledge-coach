"""Bind one private bounded skewer sample to its proof policy and owner."""

from .capture_game_trend_validate import validate as validate_cohort
from .fact_fingerprint import canonical, digest
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES, MIN_GAIN
from .protection_game_cache import _nested
from .protection_game_turns import TURN_SECONDS
from .short_mate_trend_paths import location as game_location
from .short_mate_trend_paths import source_identity
from .skewer_game_proof import MAX_ROOTS
from .skewer_game_proof import VERSION as PROOF_VERSION

VERSION = "royal-skewer-sample-v1"
OUTCOMES = ("played", "other", "unknown")


def location(db, root):
    path = game_location(db, root)
    if path is None:
        return None
    return path.with_name(path.name.removesuffix(".short-mate-trend.json") + ".skewer-v1.json")


def binding(db, learner):
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                MAX_ROOTS,
                MAX_REPLIES,
                MIN_GAIN,
                MAX_EXCHANGE_NODES,
                MAX_EXCHANGE_PLIES,
                TURN_SECONDS,
                source_identity(db, learner),
            ]
        )
    )


def valid(data, expected):
    return validate_cohort(data, expected, outcomes=OUTCOMES) and _nested(data)
