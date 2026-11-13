"""Retrieve a bounded set of operation-matched protection examples."""

from .related_capture import _assessment_options, present
from .related_protection_match import scorer
from .related_protection_source import source_for_evidence
from .related_transfer_select import select

VERSION = "protection-prevent-transfer-v2"
MAX_PROOFS = 32


def selection(
    db,
    subject,
    evidence_id,
    corpus_version,
    *,
    familiar_data=None,
    check=lambda: None,
    difficulty=None,
):
    source = source_for_evidence(db, subject, evidence_id)
    return _select(
        db, subject, source, corpus_version, VERSION, 2000, familiar_data, check, difficulty
    )


def course_selection(db, subject, source, corpus_version, *, familiar_data):
    from .related_capture_position import prompt_key
    from .tactical_course_protection import PER_BAND
    from .tactical_course_protection import VERSION as COURSE_VERSION

    familiar, _, indexed = familiar_data
    source_key = prompt_key(source["prompt_fen"])
    return _select(
        db,
        subject,
        source,
        corpus_version,
        COURSE_VERSION,
        PER_BAND,
        familiar_data,
        lambda: None,
        None,
        lambda key: key != source_key and key not in familiar and not indexed(key),
    )


def _select(
    db,
    subject,
    source,
    corpus_version,
    version,
    per_band,
    familiar_data,
    check,
    difficulty,
    prefilter=None,
):
    budget = {"checked": 0, "limit": MAX_PROOFS, "truncated": False}
    score_candidate = scorer(budget, prefilter)
    # Harder searches reuse one familiarity snapshot before reserving proof work.
    if difficulty is not None and familiar_data is None:
        from .related_capture_familiar import familiarity

        familiar_data = familiarity(db, subject)
    excluded = {"familiar": 0, "exact_source": 0}

    def score(item, features, seen, baseline):
        check()
        if difficulty is not None:
            from .protection_difficulty_filter import accepts

            if not accepts(item, source, familiar_data, difficulty, excluded):
                return None
        return score_candidate(item, features, seen, baseline)

    # Preview and admission share the same indexed band and deterministic scope.
    bounds = None if difficulty is None else (difficulty[0] * 200, difficulty[0] * 200 + 199)
    chosen = select(
        db,
        subject,
        source,
        corpus_version,
        version,
        theme="defensiveMove",
        all_lines=True,
        per_band=per_band,
        rating_bounds=bounds,
        familiar_data=familiar_data,
        feature=lambda prompt, line: dict(source["features"]),
        score=score,
    )
    if chosen is not None:
        chosen[2]["protection_scan"] = budget
        for key, count in excluded.items():
            chosen[5][key] += count
    return chosen


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    if chosen is not None:
        _assessment_options(db, result["items"], chosen[3], cursor, result["scope"])
        result["source_outcome"] = chosen[0]["outcome"]
        result["protection_scan"] = chosen[2]["protection_scan"]
        result["corpus_limited"] = chosen[2]["limited"]
    return result
