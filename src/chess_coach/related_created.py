"""Preview and atomically admit source-bound created-exposure practice."""

import time

from .fact_fingerprint import canonical, digest
from .related_capture import present
from .related_capture_familiar import familiarity
from .related_created_contract import FILTER_VERSION, KEY, VERSION
from .related_created_line import LINE_LIMIT, ROOT_LIMIT
from .related_created_match import SECONDS, scorer
from .related_created_source import source_for_evidence
from .related_session_start import start_selected
from .related_transfer_admission import admit
from .related_transfer_select import select


def selection(db, subject, evidence_id, corpus):
    frontier = (
        db.connection.execute("SELECT COALESCE(MAX(id), 0) FROM games").fetchone()[0],
        db.connection.execute("SELECT COALESCE(MAX(rowid), 0) FROM puzzle_sessions").fetchone()[0],
    )
    source = source_for_evidence(db, subject, evidence_id)
    familiar = familiarity(db, subject)
    budget = {"lines": 0, "roots": 0, "truncated": False, "deadline": time.monotonic() + SECONDS}
    chosen = select(
        db,
        subject,
        source,
        corpus,
        VERSION,
        theme="defensiveMove",
        all_lines=True,
        include_objective=True,
        familiar_data=familiar,
        per_band=101,
        feature=lambda _fen, _line: dict(source["features"]),
        score=scorer(source, familiar, budget),
    )
    if time.monotonic() >= budget["deadline"]:
        budget["truncated"] = True
    budget.pop("deadline")
    if chosen is None:
        return None
    source, rating, metadata, ordered, scope, diagnostics = chosen
    metadata["created_scan"] = {**budget, "line_limit": LINE_LIMIT, "root_limit": ROOT_LIMIT}
    # Never mint a reference from a timing-dependent partial proof set.
    if budget["truncated"]:
        ordered = []
    scope = digest(canonical([scope, VERSION, FILTER_VERSION, budget, ordered]))
    metadata["frontier"] = frontier
    return source, rating, metadata, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus)
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("created_witness", None)
    if chosen is not None:
        result["created_scan"] = chosen[2]["created_scan"]
        result["pool_limited"] = chosen[2]["limited"]
        if result["created_scan"]["truncated"]:
            result["status"] = "bounded scan exhausted; no complete selection is available"
    return result


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    chosen = selection(db, subject, evidence_id, corpus_version)
    selected = admit(chosen, reference, VERSION, "created_exposure")
    selected[3]["game_watermark"], selected[3]["legacy_watermark"] = chosen[2]["frontier"]

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key=KEY,
        resolver=lambda: selected,
    )
