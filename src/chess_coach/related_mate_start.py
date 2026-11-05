"""Atomically start a source-bound related mating example."""

from .related_mate import VERSION, selection
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start_related(
    db, *, attempt_id, subject, evidence_id, corpus_version, reference, assessment=False
):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_mate",
        resolver=lambda: _admit(db, subject, evidence_id, corpus_version, reference, assessment),
    )


def _admit(db, subject, evidence_id, corpus_version, reference, assessment):
    selection_result = selection(db, subject, evidence_id, corpus_version)
    chosen = admit(selection_result, reference, VERSION, "mate")
    source_type, version, key, binding, lines = chosen
    if assessment:
        if source_type != "corpus" or binding["mate_timing"] != "mate_within_two":
            raise ValueError("short-mate assessment unavailable")
        from .related_mate_assessment_context import capture
        from .related_mate_assessment_proof import certificate

        binding["assessment"] = certificate(db, version, key)
        source, baseline, corpus = selection_result[:3]
        try:
            context = capture(db, version, key, source, baseline, corpus)
        except (ValueError, TypeError, KeyError):
            context = None
        binding["assessment"]["context"] = context
    return source_type, version, key, binding, lines
