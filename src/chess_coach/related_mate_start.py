"""Atomically start a source-bound related mating example."""

from .related_mate import VERSION, selection
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start_related(
    db,
    *,
    attempt_id,
    subject,
    evidence_id,
    corpus_version,
    reference,
    assessment=False,
    search_state=None,
    search_secret=None,
):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_mate",
        resolver=lambda: _admit(
            db,
            subject,
            evidence_id,
            corpus_version,
            reference,
            assessment,
            search_state,
            search_secret,
        ),
    )


def _admit(
    db, subject, evidence_id, corpus_version, reference, assessment, search_state, search_secret
):
    if search_state is None:
        selection_result = selection(db, subject, evidence_id, corpus_version)
        rank_version = VERSION
    else:
        from .related_capture_cursor import PAGE
        from .related_mate_search_select import select
        from .related_mate_search_token import VERSION as rank_version

        if search_secret is None or search_state["scope"] is None:
            raise ValueError("search selection unavailable")
        selection_result, _ = select(
            db, subject, evidence_id, corpus_version, search_secret, search_state
        )
        offset = search_state["offset"]
        selection_result = (
            *selection_result[:3],
            selection_result[3][offset : offset + PAGE],
            *selection_result[4:],
        )
    chosen = admit(selection_result, reference, rank_version, "mate")
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
