"""Select and recheck one private, source-qualified exposure profile."""

import time

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .protection_finder_sources import eligible, rows
from .protection_game_source import prepare
from .related_created_source import source_for_evidence


def _profile(db, learner, evidence_id, game_id):
    source = source_for_evidence(db, learner, evidence_id)
    position = source["provenance"]["position_id"]
    row = db.connection.execute("SELECT game_id FROM positions WHERE id=?", (position,)).fetchone()
    if row is None or row["game_id"] != game_id:
        raise ValueError("profile game unavailable")
    # The identity also excludes duplicate imports of the source game.
    game = prepare(db, learner, game_id)
    features = source["features"]
    return {
        "evidence_id": evidence_id,
        "game_id": game_id,
        "position_id": position,
        "identity": game["identity"],
        "mover": features["mover"],
        "target": features["target"],
        "geometry": list(features["geometry"]),
        "source": digest(canonical(source)),
    }


def current(db, learner, profile):
    if not isinstance(profile, dict):
        raise ValueError("profile unavailable")
    return _profile(db, learner, profile["evidence_id"], profile["game_id"]) == profile


def select(db, learner, deadline):
    learner = normalize_identity(learner)
    if not learner:
        return None
    for row in rows(db, learner, 0, 2**63 - 1, 0):
        if time.monotonic() >= deadline:
            return None
        if not eligible(row, 0):
            continue
        try:
            return _profile(db, learner, row["id"], row["game_id"])
        except (ValueError, TypeError, KeyError, IndexError, StopIteration):
            continue
    return None


def features(profile):
    return {
        "mover": profile["mover"],
        "target": profile["target"],
        "geometry": tuple(profile["geometry"]),
    }
