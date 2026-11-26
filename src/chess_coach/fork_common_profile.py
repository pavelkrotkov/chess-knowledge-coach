"""Qualify one fork context with its actual first assessment result."""

from .capture_context_presence import sample
from .fact_fingerprint import canonical
from .fork_common_source import bind
from .fork_context_presence import pattern, turn


def profile(db, subject, corpus, as_of, report, check):
    if report["historical"] or not report["comparable"] or not report["boundary"]:
        return None
    source = bind(db, subject, corpus, as_of, report, check)
    if source is None:
        return None
    source_turn, root = source["turn"], source["root"]
    context = canonical(
        [
            source_turn["side"],
            source_turn["time_control"],
            source_turn["phase"],
            source_turn["material"],
        ]
    )
    wanted = (context, pattern(root))
    newer = sample(report["newer"], wanted, check, turn=turn)
    earlier = sample(report["earlier"], wanted, check, turn=turn)
    if not newer["qualified"] or not earlier["qualified"]:
        return None
    return {**source, "newer": newer, "earlier": earlier}
