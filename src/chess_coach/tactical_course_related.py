"""Build one source-bound unfamiliar worked example, when available."""

from .course_guidance import attribution
from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .related_capture import VERSION as CAPTURE_VERSION
from .related_capture import _selection as capture_selection
from .related_fork import VERSION as FORK_VERSION
from .related_fork import selection as fork_selection
from .related_mate import VERSION as MATE_VERSION
from .related_mate import selection as mate_selection
from .related_transfer_admission import admit
from .unified_sources import resolve_source

FORK_CORPUS = "fork corpus unavailable"
FORK_EMPTY = "no compatible unfamiliar fork in the bounded scan"
HISTORY_LIMIT = "familiarity history exceeds the bounded scan"
GENERAL_EMPTY = "related corpus or compatible unfamiliar example unavailable"


def _selection(db, subject, corpus, choice, familiar_data):
    kind = choice["kind"]
    if kind == "protection":
        return None, None, None
    if kind == "capture":
        selected = capture_selection(
            db, subject, choice["position_id"], corpus, familiar_data=familiar_data
        )
        return selected, CAPTURE_VERSION, "material_capture"
    if kind == "fork":
        selected = fork_selection(
            db, subject, choice["evidence_id"], corpus, familiar_data=familiar_data
        )
        return selected, FORK_VERSION, "fork"
    selected = mate_selection(
        db, subject, choice["evidence_id"], corpus, familiar_data=familiar_data
    )
    return selected, MATE_VERSION, "mate"


def with_reason(db, subject, corpus, choice, *, familiar_data=None):
    selected, version, motif = _selection(db, subject, corpus, choice, familiar_data)
    if selected is None:
        return None, FORK_CORPUS if choice["kind"] == "fork" else GENERAL_EMPTY
    if not selected[3]:
        return None, FORK_EMPTY if choice["kind"] == "fork" else GENERAL_EMPTY
    # Selection already excludes familiar prompts and binds the source.
    # Reuse its first bounded match without running an assessment verifier.
    if selected[0]["provenance"]["evidence_id"] != choice["evidence_id"]:
        raise ValueError("related source differs from selected lesson")
    item, scope = selected[3][0], selected[4]
    reference = digest(canonical([scope, item["type"], item["version"], item["key"]]))
    source_type, source_version, key, binding, matching = admit(selected, reference, version, motif)
    snapshot = resolve_source(db, source_type, source_version, key, subject=subject)
    if matching is not None:
        snapshot = {**snapshot, "lines": matching}
    provenance = {"type": source_type, "version": source_version, "key": key, "binding": binding}
    credit = attribution(db, source_type, source_version, snapshot)
    note = f"Pattern-cued unfamiliar worked example; other legal moves are ungraded. {credit}"
    return chapter("Related unfamiliar example", note, snapshot, provenance), None


def unfamiliar(db, subject, corpus, choice, *, familiar_data=None):
    return with_reason(db, subject, corpus, choice, familiar_data=familiar_data)[0]
