"""Selection provenance stays explicit and matches imported identities."""

import json
import sqlite3

import pytest

from chess_coach.puzzle_selection import validate_selection
from chess_coach.puzzle_selection_schema import add_puzzle_selection


def manifest():
    return {
        "policy": "source_order_prefix",
        "fullsource_count": 100,
        "selected_count": 2,
        "parent_csv_sha256": "a" * 64,
        "parent_archive_sha256": "b" * 64,
        "derived_csv_sha256": "c" * 64,
        "representative": False,
    }


def test_schema_preserves_existing_rows_and_is_idempotent():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE puzzle_imports (corpus_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO puzzle_imports VALUES (1)")
    add_puzzle_selection(connection)
    add_puzzle_selection(connection)
    assert connection.execute("SELECT selection_json FROM puzzle_imports").fetchone() == (None,)


def test_canonical_manifest_and_bound_identities():
    result = validate_selection(manifest(), "c" * 64, "b" * 64)
    assert json.loads(result) == manifest()
    assert result == validate_selection(
        dict(reversed(list(manifest().items()))), "c" * 64, "b" * 64
    )
    with pytest.raises(ValueError, match="identity"):
        validate_selection(manifest(), "d" * 64, "b" * 64)
    with pytest.raises(ValueError, match="identity"):
        validate_selection(manifest(), "c" * 64, "d" * 64)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"policy": "random"}, "policy"),
        ({"representative": True}, "policy"),
        ({"fullsource_count": True}, "counts"),
        ({"selected_count": 0}, "counts"),
        ({"selected_count": 101}, "counts"),
        ({"fullsource_count": 2**63}, "counts"),
        ({"parent_csv_sha256": "broken"}, "digest"),
        ({"extra": 1}, "fields"),
    ],
)
def test_invalid_selection(change, message):
    with pytest.raises(ValueError, match=message):
        validate_selection(manifest() | change, "c" * 64, "b" * 64)
