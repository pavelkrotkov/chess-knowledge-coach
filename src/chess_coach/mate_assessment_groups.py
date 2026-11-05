"""Summarize first and later distinct-prompt assessment samples."""

from collections import defaultdict

from .mate_assessment_compare import SAMPLE, comparable
from .mate_assessment_group_counts import counts


def groups(items, limited):
    grouped = defaultdict(list)
    for item in items:
        if item["scope"]:
            grouped[item["scope"]["key"]].append(item)
    output = []
    for values in grouped.values():
        can_compare = comparable(values, limited)
        output.append(
            {
                "count": len(values),
                "baseline": counts(values[:SAMPLE]),
                "rating_start": values[0]["scope"]["rating_start"],
                "deviation_start": values[0]["scope"]["deviation_start"],
                "comparable": can_compare,
                "earlier": counts(values[:SAMPLE]) if can_compare else None,
                "later": counts(values[-SAMPLE:]) if can_compare else None,
            }
        )
    return output
