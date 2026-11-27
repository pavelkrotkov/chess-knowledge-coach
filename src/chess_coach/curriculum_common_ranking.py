"""Compare the exact staged capture and fork candidates."""

from .capture_game_trend_report import report as capture_report
from .curriculum_capture_rank import choice
from .fork_capture_comparison import compare
from .fork_game_trend_report import report as fork_report


def _comparison(db, state, subject, root, option, fork, check, bundle, capture):
    corpus, as_of = state["corpus_version"], state["as_of"]
    report = fork_report(db, subject, root, check=check, as_of=as_of)
    if not report:
        return None
    return compare(
        db,
        subject,
        corpus,
        root,
        as_of,
        report,
        check,
        capture_option=option,
        fork_evidence=fork["source_evidence_id"],
        admitted=(fork, bundle["fork_status"], bundle["fork_focus"]),
        capture_observation=capture,
    )


def _reason(result, winner):
    own = result[winner]["newer"]
    other = "fork" if winner == "capture" else "capture"
    theirs = result[other]["newer"]
    return (
        f"The first unassisted assessment for this {winner} source was incorrect; "
        f"the comparable {other} source was correct. "
        "Matching opportunities occurred in {} to {} of {} recent games for this source, "
        "and {} to {} of {} for the other source."
    ).format(
        own["lower"],
        own["upper"],
        own["denominator"],
        theirs["lower"],
        theirs["upper"],
        theirs["denominator"],
    )


def rank(db, state, subject, root, options, fork, matched, check, bundle):
    capture_report_value = capture_report(db, subject, root, check=check, as_of=state["as_of"])
    chosen, rationale = choice(
        db, subject, state, options, matched, check, root=root, report=capture_report_value
    )
    capture, focus = options[chosen]
    blocked = matched | set(state["seen"])
    eligible = capture["prompt_key"] not in blocked and fork["prompt_key"] not in blocked
    result = None
    if eligible and capture["prompt_key"] != fork["prompt_key"]:
        result = _comparison(
            db, state, subject, root, options[chosen], fork, check, bundle, capture_report_value
        )
    winner = None
    if result is not None:
        winner = (
            "capture"
            if result["capture"]["source"]["practice"]["result"] == "incorrect"
            else "fork"
        )
        state["common"]["winner"] = winner
    return capture, focus, blocked, rationale, winner, _reason(result, winner) if winner else None
