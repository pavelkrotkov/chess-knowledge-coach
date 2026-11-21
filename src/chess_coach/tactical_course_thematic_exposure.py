"""Check known tactical deliveries for one worked companion."""

from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .related_capture_candidates import _game_id
from .related_capture_position import prompt_key
from .tactical_exposure_check import coverage
from .tactical_exposure_intents import check_intents
from .tactical_exposure_lookup import ledger_check
from .unified_sources import resolve_source


def exposure(db, subject, key, artifact):
    identity = normalize_identity(subject)
    if not identity:
        raise ValueError("exposure subject unavailable")
    now = datetime.now(UTC)
    intent = check_intents(db, identity, key, now, ignore_artifact=artifact)
    if intent != "not_recorded":
        return intent
    start = coverage(db)
    if start is None:
        return "legacy_coverage_unknown"
    return ledger_check(db, identity, key, now, start, intent, ignore_artifact=artifact)


def candidate(db, subject, corpus, row, own, familiar_data, artifact):
    familiar, games, indexed = familiar_data
    game = _game_id(row["source"])
    if game in games:
        return None
    try:
        snapshot = resolve_source(db, "corpus", corpus, row["puzzle_id"], subject=subject)
        key = prompt_key(snapshot["prompt_fen"])
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    if key == prompt_key(own["prompt_fen"]) or key in familiar or indexed(key):
        return None
    exposed = exposure(db, subject, key, artifact)
    if exposed not in {"not_recorded", "legacy_coverage_unknown"}:
        return None
    return snapshot, exposed
