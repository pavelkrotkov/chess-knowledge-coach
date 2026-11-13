"""Retrieve a bounded unfamiliar response to an anchored back-rank threat."""

from .fact_fingerprint import canonical, digest
from .recurrence_snapshot import read_snapshot
from .related_backrank_contract import DEFENSE_FILTER_VERSION, DEFENSE_VERSION
from .related_backrank_defense_match import PROOF_LIMIT, scorer
from .related_backrank_defense_source import UnsupportedDefense, source_for_evidence
from .related_capture import present
from .related_capture_familiar import familiarity
from .related_session_start import start_selected
from .related_transfer_admission import admit
from .related_transfer_select import select


def selection(db, subject, evidence_id, corpus_version):
    with read_snapshot(db):
        source = source_for_evidence(db, subject, evidence_id)
        budget = {
            "proofs": 0,
            "proof_limit": PROOF_LIMIT,
            "truncated": False,
            "familiar": 0,
            "exact_source": 0,
        }
        familiar_data = familiarity(db, subject)
        chosen = select(
            db,
            subject,
            source,
            corpus_version,
            DEFENSE_VERSION,
            theme="defensiveMove",
            all_lines=True,
            include_objective=True,
            feature=lambda _prompt, _line: dict(source["features"]),
            score=scorer(source, budget, familiar_data),
            familiar_data=familiar_data,
        )
        if chosen is None:
            return None
        source, rating, corpus, ordered, scope, diagnostics = chosen
        corpus["defense_scan"] = budget
        scope = digest(canonical([scope, DEFENSE_VERSION, DEFENSE_FILTER_VERSION, budget, ordered]))
        return source, rating, corpus, ordered, scope, diagnostics


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    try:
        chosen = selection(db, subject, evidence_id, corpus_version)
    except UnsupportedDefense as error:
        return {"status": str(error), "items": [], "next_cursor": None}
    result = present(chosen, cursor)
    for item in result["items"]:
        item.pop("defense_witness", None)
    if chosen is not None:
        result["defense_scan"] = chosen[2]["defense_scan"]
    return result


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    chosen = selection(db, subject, evidence_id, corpus_version)
    selected = admit(chosen, reference, DEFENSE_VERSION, "backrank_defense")

    def current_selection():
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("transfer selection changed; preview again")
        return selected

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_backrank_defense",
        resolver=current_selection,
    )
