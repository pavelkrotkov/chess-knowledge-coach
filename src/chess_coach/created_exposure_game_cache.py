"""Versioned bounded cache for one created-exposure profile."""

from .capture_game_trend_validate import validate as validate_cohort
from .created_exposure_game_contrast import ROOT_LIMIT
from .created_exposure_game_proof import VERSION as PROOF_VERSION
from .created_exposure_game_sample import TURN_SECONDS
from .fact_fingerprint import canonical, digest
from .objective_created_contract import VERIFIER
from .protection_game_cache import _nested
from .short_mate_trend_paths import location as game_location
from .short_mate_trend_paths import source_identity

VERSION = "created-exposure-game-coverage-v1"
OUTCOMES = ("no_nominee", "protected", "missed", "opportunity_unresolved", "unknown")


def location(db, root):
    path = game_location(db, root)
    if path is None:
        return None
    return path.with_name(
        path.name.removesuffix(".short-mate-trend.json") + ".created-exposure-v1.json"
    )


def binding(db, learner):
    return digest(
        canonical(
            [
                VERSION,
                PROOF_VERSION,
                VERIFIER,
                ROOT_LIMIT,
                TURN_SECONDS,
                source_identity(db, learner),
            ]
        )
    )


def _prefix(item):
    return all(row[1] == "no_nominee" for row in item["results"][:-1])


def _independent(item, profile):
    return (
        item["id"] != profile.get("game_id")
        and item["identity"] != profile.get("identity")
        and _prefix(item)
    )


def valid(data, expected):
    profile = data.get("profile")
    if not isinstance(profile, dict):
        return False
    return (
        validate_cohort(data, expected, outcomes=OUTCOMES)
        and _nested(data)
        and all(
            _independent(item, profile) for item in [*data["games"], *data["retained"].values()]
        )
    )
