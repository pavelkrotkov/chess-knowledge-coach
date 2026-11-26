"""Compare eligible capture candidates against their exact dated contexts."""

from .capture_context_comparison import _comparison, _profile
from .capture_game_trend_report import report as capture_trend_report
from .curriculum_priority_cursor import CONTEXT_CAPTURE_POLICY


def _profiles(db, subject, corpus, as_of, report, options, observations, check):
    if not report or not report["comparable"] or not report["boundary"] or report["historical"]:
        return None
    profiles = [
        _profile(db, subject, corpus, as_of, report, option, check, observed=observed)
        for option, observed in zip(options, observations, strict=True)
    ]
    return None if None in profiles else profiles


def choice(db, subject, state, root, options, observations, check):
    if state["priority_policy"] != CONTEXT_CAPTURE_POLICY or root is None or None in observations:
        return None
    corpus, as_of = state["corpus_version"], state["as_of"]
    report = capture_trend_report(db, subject, root, check=check, as_of=as_of)
    profiles = _profiles(db, subject, corpus, as_of, report, options, observations, check)
    if profiles is None:
        return None
    winner = _comparison(*profiles)["winner"]
    if winner is None:
        return None
    chosen, other = profiles[winner]["newer"], profiles[1 - winner]["newer"]
    tier = profiles[winner]["source"]["practice"]["result"]
    rationale = (
        f"Comparable verified {tier} practice; "
        f"matched capture opportunities appeared in {chosen['lower']} to {chosen['upper']} "
        f"of {chosen['denominator']} recent games versus {other['lower']} to {other['upper']} "
        f"of {other['denominator']} for the other context."
    )
    return winner, rationale
