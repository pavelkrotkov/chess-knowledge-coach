"""Reserve one unit before inspecting a supplied back-rank line."""

from .related_backrank_contract import LINE_LIMIT


def take(budget):
    if budget["lines"] >= LINE_LIMIT:
        budget["truncated"] = True
        return False
    budget["lines"] += 1
    return True
