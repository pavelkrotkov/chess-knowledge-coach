"""Classify bounded branches and identify actual transpositions."""


def _unique(graphs):
    return {tuple(graph["edges"]): graph for graph in graphs}.values()


def _kind(graph, history):
    missing = [
        parent
        for edge, parent in zip(graph["edges"], graph["positions"], strict=False)
        if edge not in history["edges"]
    ]
    if not missing:
        return "shared"
    if all(parent in history["positions"] for parent in missing):
        return "revised"
    return "new"


def partitions(graphs, history):
    result = {"shared_branches": None, "revised_branches": None, "new_branches": None}
    if history is None:
        return result
    kinds = [_kind(graph, history) for graph in _unique(graphs)]
    result["shared_branches"] = kinds.count("shared")
    if not history["incomplete"]:
        result["revised_branches"] = kinds.count("revised")
        result["new_branches"] = kinds.count("new")
    return result


def transpositions(graphs):
    incoming = {}
    for graph in graphs:
        for edge, child in zip(graph["edges"], graph["positions"][1:], strict=True):
            incoming.setdefault(child, set()).add(edge)
    return sum(len(edges) > 1 for edges in incoming.values())
