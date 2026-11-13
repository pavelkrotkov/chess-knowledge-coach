"""Recheck a played move that exposed a previously unthreatened piece."""

import sqlite3

from .material_created_exposure_proof import proof
from .material_observation import material_observation
from .material_opportunities import inspect_material_opportunity
from .material_opportunity_current import _same_source
from .material_opportunity_source import load_source
from .material_source import prepare


def explain(db, evidence, subject):
    if not _eligible(evidence):
        return None
    try:
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        prepared = _prepared(db, evidence, subject)
        if prepared is None:
            return None
        result = proof(*prepared)
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            return None
        return result
    except (ValueError, TypeError, KeyError, IndexError, StopIteration, sqlite3.Error):
        return None


def _prepared(db, evidence, subject):
    view = inspect_material_opportunity(db, evidence["id"], learner=subject)
    if not all(
        (
            view["currentness"] == "current",
            view["family_validated"],
            view["outcome"] == "failure",
            view["objective"]["kind"] == "material_protection",
            view["review_status"] in {"accepted", "unreviewed"},
        )
    ):
        return None
    prepared = prepare(db, view["position_id"], subject)
    source = load_source(db, view["lineage"]["detector_run_id"])
    fact = next(f["payload"] for f in evidence["facts"] if f["id"] == view["lineage"]["fact_id"])
    if not _same_source(prepared, source):
        return None
    # The exercise witness requires a prior threat; replay the observation for this lesson.
    observed = material_observation(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    if observed != fact:
        return None
    return prepared, fact


def _eligible(evidence):
    return all(
        (
            evidence["material_source_currentness"] == "current",
            evidence["operation"] == "prevent",
            evidence["outcome"] == "failure",
            evidence["review_status"] in {"accepted", "unreviewed"},
        )
    )
