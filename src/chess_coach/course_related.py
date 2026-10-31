"""Select and admit unfamiliar related course practice."""

from .course_guidance import attribution, objective
from .course_pgn import chapter
from .fact_fingerprint import canonical, digest
from .related_capture import VERSION as CAPTURE_VERSION
from .related_capture import _selection as capture_selection
from .related_mate import VERSION as MATE_VERSION
from .related_mate import selection as mate_selection
from .related_transfer_admission import admit
from .unified_sources import resolve_source


def related(db, subject, corpus, choice, kind):
    if kind == "capture":
        selection = capture_selection(db, subject, choice["position_id"], corpus)
        version, motif = CAPTURE_VERSION, "material_capture"
    else:
        selection = mate_selection(db, subject, choice["evidence_id"], corpus)
        version, motif = MATE_VERSION, "mate"
    if selection is None or not selection[3]:
        raise ValueError("related practice unavailable")
    item, scope = selection[3][0], selection[4]
    reference = digest(canonical([scope, item["type"], item["version"], item["key"]]))
    source_type, source_version, key, binding, matching = admit(
        selection, reference, version, motif
    )
    snapshot = resolve_source(db, source_type, source_version, key, subject=subject)
    if matching is not None:
        snapshot = {**snapshot, "lines": matching}
    provenance = {"type": source_type, "version": source_version, "key": key, "binding": binding}
    title = "A new material-gain exercise" if kind == "capture" else "A new checkmate exercise"
    source_credit = attribution(db, source_type, source_version, snapshot)
    note = f"Unfamiliar library exercise selected for the same pattern. {source_credit}"
    note, interactive = objective(note, snapshot, kind)
    return chapter(title, note, snapshot, provenance, gamebook=interactive)
