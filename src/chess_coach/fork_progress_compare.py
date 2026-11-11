"""Replay two bounded samples against their exact source and event records."""

import json

from .fork_history_item import item
from .fork_progress_bounds import direction
from .fork_progress_samples import sample
from .mate_assessment_compare import SAMPLE, ordered


def _entries(db, rows, corpus, budget):
    found, cache = [], {}
    for row in rows:
        with budget.scope(snapshot=False):
            found.append(item(db, row, corpus, budget.check, cache=cache))
    return found


def comparison(db, group, corpus, budget):
    report = {"status": "withheld", "group_size": len(group)}
    if not ordered(group):
        report["reason"] = "ambiguous_boundary"
        return report
    entries = _entries(db, group[:SAMPLE] + group[-SAMPLE:], corpus, budget)
    earlier, recent = sample(entries[:SAMPLE]), sample(entries[SAMPLE:])
    context = json.loads(group[0]["provenance_json"])["related_fork"]["assessment"]["context"]
    report.update(
        earlier=earlier,
        recent=recent,
        rating_start=200 * context["rating_band"],
        deviation_start=100 * context["deviation_band"],
        direction=direction(earlier, recent),
    )
    return report
