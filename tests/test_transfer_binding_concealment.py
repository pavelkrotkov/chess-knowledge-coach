"""Verify named binding digests and retain all other answer content."""

import copy

import pytest

from tests.test_transfer_concealment_support import SOURCE
from tests.transfer_concealment_support import binding_text
from tests.transfer_expected_support import digest


def test_real_sha_snapshot_collision_remains_concealed():
    expected = {"source_fingerprint": "a" * 64, "source_snapshot_hash": digest(SOURCE)}
    binding = dict(expected) | {"motif": "fork"}
    assert "b5c7" in expected["source_snapshot_hash"]
    assert "b5c7" not in binding_text(binding, expected)


@pytest.mark.parametrize(
    "field", ["source_fingerprint", "source_snapshot_hash", "source_lines_hash"]
)
def test_invalid_or_changed_binding_digest_fails(field):
    expected = {
        "source_fingerprint": "a" * 64,
        "source_snapshot_hash": digest(SOURCE),
        "source_lines_hash": "c" * 64,
    }
    binding = copy.deepcopy(expected)
    binding[field] = "b" * 64
    with pytest.raises(AssertionError):
        binding_text(binding, expected)


def test_unapproved_binding_fields_and_nonhex_keys_are_not_masked():
    expected = {"source_fingerprint": "a" * 64, "source_snapshot_hash": digest(SOURCE)}
    binding = dict(expected) | {"extra": {"answer": "b5c7", "key": "fork-good"}}
    text = binding_text(binding, expected)
    assert "b5c7" in text and "fork-good" in text
