"""Validate competency endpoints, relations and acyclic dependencies."""

EDGE_TYPES = {"contains", "requires", "supports"}


def validate_graph(skills, edges) -> None:
    """Reject unknown endpoints, relation types, duplicate edges and directed cycles."""
    if not skills or any(not key or not value for key, value in skills.items()):
        raise ValueError("skills and descriptions must not be empty")
    if len(edges) != len(set(edges)):
        raise ValueError("duplicate competency edge")
    outgoing = {skill: set() for skill in skills}
    for parent, child, relation in edges:
        _validate_edge(skills, parent, child, relation)
        outgoing[parent].add(child)
    _check_cycles(outgoing)


def _validate_edge(skills, parent, child, relation) -> None:
    if parent not in skills or child not in skills:
        raise ValueError("competency edge references an unknown skill")
    if relation not in EDGE_TYPES:
        raise ValueError("unknown competency edge type")


def _check_cycles(outgoing) -> None:
    remaining = {key: set(value) for key, value in outgoing.items()}
    while remaining:
        leaves = {key for key, children in remaining.items() if not children}
        if not leaves:
            raise ValueError("competency graph has a cycle")
        remaining = {
            key: children - leaves for key, children in remaining.items() if key not in leaves
        }
