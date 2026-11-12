"""Validate the sidecar envelope and examined source sequence."""

from .capture_game_trend_relations import valid_relations
from .short_mate_game_counts import OUTCOMES
from .short_mate_trend_records import games, retained


# Cache records are private derived data, but checksum validation alone does
# not establish that their source IDs, signatures and game decisions agree.
# Bound each sequence before accepting it for a worker or read-only report.
def _source(row):
    return (
        isinstance(row, list)
        and len(row) == 2
        and type(row[0]) is int
        and row[0] > 0
        and isinstance(row[1], str)
    )


def _checked(data):
    checked = data.get("checked")
    if not isinstance(checked, list) or len(checked) > 100:
        return False
    if type(data.get("index")) is not int or data["index"] != len(checked):
        return False
    return all(map(_source, checked))


def _metadata(data):
    return (
        isinstance(data.get("frontier"), str)
        and type(data.get("selection_complete")) is bool
        and type(data.get("rotation", 0)) is int
        and type(data.get("unavailable")) is int
        and type(data.get("duplicates")) is int
    )


# Historical selection requires 41 independent games. The final game is the
# comparison boundary; all examined duplicates and unavailable rows must also
# account for their positions in the checked sequence.
def independent(data):
    """Prove a complete cohort has linked, unique sources and results."""
    checked = data["checked"]
    counts_match = len(data["games"]) + data["duplicates"] + data["unavailable"] == len(checked)
    return (
        len(data["games"]) == 41
        and len({row[0] for row in checked}) == len(checked)
        and min(data["duplicates"], data["unavailable"]) >= 0
        and counts_match
        and valid_relations(data, checked)
    )


# Keep at most one earlier complete selection. Nested history would defeat the
# size and source bounds, so reject it instead of traversing an unbounded chain.
def _prior(data, expected, outcomes):
    prior = data.get("prior")
    if prior is None:
        return True
    if not isinstance(prior, dict) or prior.get("prior") is not None:
        return False
    return (
        valid(prior, expected, outcomes=outcomes)
        and prior["selection_complete"]
        and not prior["retained"]
        and isinstance(prior.get("coverage"), dict)
        and independent(prior)
    )


def valid(data, expected, *, outcomes=OUTCOMES):
    if not isinstance(data, dict) or data.get("binding") != expected:
        return False
    return (
        _checked(data)
        and _metadata(data)
        and games(data.get("games"), outcomes)
        and retained(data.get("retained"), outcomes)
        and _prior(data, expected, outcomes)
    )
