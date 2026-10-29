"""Apply only explicitly bound fork-line subsets to a session snapshot."""

from .related_fork_lines import select_lines


def apply_filter(snapshot, provenance, provenance_key, line_filter):
    if provenance_key == "related_fork":
        select_lines(snapshot, provenance)
        if snapshot["lines"] != line_filter:
            raise ValueError("practice line selection unavailable")
    elif line_filter is not None:
        raise ValueError("unsupported practice line selection")
