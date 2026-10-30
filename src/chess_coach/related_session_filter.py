"""Apply only explicitly bound fork-line subsets to a session snapshot."""

from .related_fork_lines import FILTER_VERSION, select_lines
from .related_protection_contract import FILTER_VERSION as PROTECTION_FILTER


def apply_filter(snapshot, provenance, provenance_key, line_filter):
    if provenance_key in {"related_fork", "related_protection"}:
        version = PROTECTION_FILTER if provenance_key == "related_protection" else FILTER_VERSION
        select_lines(snapshot, provenance, expected_version=version)
        if snapshot["lines"] != line_filter:
            raise ValueError("practice line selection unavailable")
    elif line_filter is not None:
        raise ValueError("unsupported practice line selection")
