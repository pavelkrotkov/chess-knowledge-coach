"""Compare a bounded public response graph with checked same-side history."""


def _sets(graphs):
    positions, edges, responses = set(), {}, set()
    for graph in graphs:
        positions.update(graph["positions"])
        edges.update(zip(graph["edges"], graph["positions"], strict=False))
        if len(graph["edges"]) > 1:
            responses.add(graph["edges"][1])
    return positions, edges, responses


def counts(graphs, history):
    positions, edges, responses = _sets(graphs)
    result = {"positions": len(positions), "edges": len(edges), "responses": len(responses)}
    if history is None:
        result.update(shared_positions=None, shared_edges=None, shared_responses=None)
    else:
        result.update(
            shared_positions=len(positions & history["positions"]),
            shared_edges=len(set(edges) & history["edges"]),
            shared_responses=len(responses & history["edges"]),
        )
    result.update(new_positions=None, revised_edges=None, new_edges=None)
    if history is not None and not history["incomplete"]:
        seen_positions, seen_edges = history["positions"], history["edges"]
        result.update(
            new_positions=len(positions - seen_positions),
            revised_edges=sum(
                edge not in seen_edges and parent in seen_positions
                for edge, parent in edges.items()
            ),
            new_edges=sum(
                edge not in seen_edges and parent not in seen_positions
                for edge, parent in edges.items()
            ),
        )
    return result
