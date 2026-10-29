"""Group source-linked observations and their descriptive strata."""

from collections import defaultdict

from .recurrence_context import context
from .recurrence_counts import counts


def summarize(items):
    groups = defaultdict(list)
    for item in items:
        groups[(item["skill"], item["operation"], item["family"], item["version"])].append(item)
    output = []
    for key, values in sorted(groups.items()):
        strata = defaultdict(list)
        for item in values:
            for field, value in context(item["decision"]).items():
                strata[(field, value)].append(item)
        output.append(
            {
                "skill": key[0],
                "operation": key[1],
                "family": key[2],
                "version": key[3],
                **counts(values),
                "strata": [
                    {"field": k[0], "value": k[1], **counts(v)} for k, v in sorted(strata.items())
                ],
                "examples": [
                    {
                        k: item[k]
                        for k in (
                            "id",
                            "position_id",
                            "game_id",
                            "ply",
                            "outcome",
                            "review",
                            "currentness",
                        )
                    }
                    for item in values[:10]
                ],
            }
        )
    return output
