"""Bind a fork session to its selected lines and full source snapshot."""

from .fact_fingerprint import canonical, digest

FILTER_VERSION = "fork-execute-lines-v1"


def select_lines(snapshot, binding, *, expected_version=None):
    """Validate source-line identity and keep the recorded matching indices."""
    if expected_version is None:
        expected_version = FILTER_VERSION
    lines = snapshot["lines"]
    indices = binding["selected_line_indices"]
    if binding["line_filter_version"] != expected_version:
        raise ValueError("practice line filter changed")
    if digest(canonical(lines)) != binding["source_lines_hash"]:
        raise ValueError("practice source lines changed")
    if not _valid_indices(indices, len(lines)):
        raise ValueError("practice line selection unavailable")
    snapshot["lines"] = [lines[index] for index in indices]


def _valid_indices(indices, length):
    return (
        isinstance(indices, list)
        and bool(indices)
        and all(type(index) is int and 0 <= index < length for index in indices)
        and indices == sorted(set(indices))
    )


def bind_lines(item, lines, indices):
    item["matching_lines"] = [lines[index] for index in indices]
    item["matching_line_indices"] = indices
    item["source_lines_hash"] = digest(canonical(lines))
