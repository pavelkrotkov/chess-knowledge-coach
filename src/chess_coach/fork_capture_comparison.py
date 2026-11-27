"""Compare independently qualified capture and fork first assessments."""

from .capture_game_trend_report import report as capture_report
from .dated_game_cohort_identity import identity
from .fork_capture_lineage import profiles as qualified_profiles


def compare(
    db,
    subject,
    corpus,
    root,
    as_of,
    fork,
    check,
    *,
    capture_option=None,
    fork_evidence=None,
    admitted=None,
    capture_observation=None,
):
    capture = capture_observation
    if capture is None:
        capture = capture_report(db, subject, root, check=check, as_of=as_of)
    cohort = identity(capture)
    if cohort is None or cohort != identity(fork):
        return None
    profiles = qualified_profiles(
        db, subject, corpus, as_of, capture, fork, check, capture_option, admitted
    )
    if profiles is None:
        return None
    left, right = profiles
    if fork_evidence is not None and right["practice"]["binding"]["evidence_id"] != fork_evidence:
        return None
    capture_result = left["source"]["practice"]["result"]
    fork_result = right["practice"]["result"]
    if capture_result == fork_result:
        return None
    return {"capture": left, "fork": right}
