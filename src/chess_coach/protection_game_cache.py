"""Private versioned sidecar for bounded independent protection observations."""

from .capture_game_trend_validate import validate as validate_cohort
from .fact_fingerprint import canonical, digest
from .material_capture_gain import MIN_GAIN
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES
from .objective_protection_before import MAX_CAPTURES
from .objective_protection_judge import VERSION as JUDGE_VERSION
from .protection_game_proof import ROOT_LIMIT
from .protection_game_proof import VERSION as PROOF_VERSION
from .protection_game_turns import TURN_SECONDS
from .short_mate_trend_paths import location as game_location
from .short_mate_trend_paths import source_identity

VERSION = "protection-game-coverage-v1"
OUTCOMES = ("no_opportunity", "protected", "missed", "opportunity_unresolved", "unknown")


def location(db, root):
    path = game_location(db, root)
    if path is None:
        return None
    return path.with_name(path.name.removesuffix(".short-mate-trend.json") + ".protection-v1.json")


def binding(db, learner):
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                JUDGE_VERSION,
                ROOT_LIMIT,
                TURN_SECONDS,
                MIN_GAIN,
                MAX_CAPTURES,
                MAX_REPLIES,
                MAX_EXCHANGE_NODES,
                MAX_EXCHANGE_PLIES,
                source_identity(db, learner),
            ]
        )
    )


def _stamp(value):
    return value is None or (isinstance(value, str) and len(value) == 64)


def _game(item):
    # Nonempty results require the exact analysis and review stamps used to produce them.
    values = [item.get(key) for key in ("analysis", "review")]
    return all(map(_stamp, values)) and (not item["results"] or None not in values)


def _nested(data):
    # Retained and prior games can resume only with the same source binding.
    values = [*data["games"], *data["retained"].values()]
    if not all(_game(item) for item in values):
        return False
    prior = data.get("prior")
    return prior is None or _nested(prior)


def valid(data, expected):
    return validate_cohort(data, expected, outcomes=OUTCOMES) and _nested(data)
