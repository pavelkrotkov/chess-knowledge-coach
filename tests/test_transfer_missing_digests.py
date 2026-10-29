"""Missing source identities cannot be treated as safe opaque values."""

import pytest

from tests.test_transfer_concealment_support import SELECTION
from tests.transfer_concealment_support import binding_text, preview_text
from tests.transfer_expected_support import references


@pytest.mark.parametrize("missing", ["scope", "reference"])
def test_missing_preview_digest_is_rejected(missing):
    payload = {"scope": SELECTION[4], "items": [{"reference": references(SELECTION)[0]}]}
    mapping = payload if missing == "scope" else payload["items"][0]
    del mapping[missing]
    with pytest.raises((AssertionError, KeyError)):
        preview_text(payload, SELECTION)


@pytest.mark.parametrize(
    "missing", ["source_fingerprint", "source_snapshot_hash", "source_lines_hash"]
)
def test_missing_binding_digest_is_rejected(missing):
    expected = {
        "source_fingerprint": "a" * 64,
        "source_snapshot_hash": "b" * 64,
        "source_lines_hash": "c" * 64,
    }
    binding = dict(expected)
    del binding[missing]
    with pytest.raises((AssertionError, KeyError)):
        binding_text(binding, expected)
