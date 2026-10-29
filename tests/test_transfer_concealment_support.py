"""Named, independently verified hashes do not hide transfer answer content."""

import pytest

from tests.transfer_concealment_support import preview_text
from tests.transfer_expected_support import references

SCOPE = "b5c7" + "a" * 60
SOURCE = {"provenance": {"source_fingerprint": "a" * 64}, "nonce": 711}
# This fixture key produces a genuine SHA-256 reference containing the move text.
ITEM = {"type": "corpus", "version": "v", "key": "2118"}
SELECTION = (SOURCE, None, None, [ITEM], SCOPE, None)


def test_real_sha_reference_and_scope_collision_remain_concealed():
    ref = references(SELECTION)[0]
    payload = {"scope": SCOPE, "items": [{"reference": ref, "description": "fixture"}]}
    assert "b5c7" in ref and "b5c7" in SCOPE
    assert "b5c7" not in preview_text(payload, SELECTION)
    assert payload["scope"] == SCOPE and payload["items"][0]["reference"] == ref


@pytest.mark.parametrize("location", ["description", "data", "other_hash"])
def test_unapproved_preview_fields_cannot_hide_an_answer(location):
    payload = {"scope": SCOPE, "items": [{"reference": references(SELECTION)[0]}]}
    payload["items"][0][location] = {"answer": "b5c7"}
    assert "b5c7" in preview_text(payload, SELECTION)


@pytest.mark.parametrize("field", ["scope", "reference"])
def test_invalid_or_changed_preview_digest_fails(field):
    payload = {"scope": SCOPE, "items": [{"reference": references(SELECTION)[0]}]}
    if field == "scope":
        payload["scope"] = "b" * 64
    else:
        payload["items"][0]["reference"] = "b5c7-invalid"
    with pytest.raises(AssertionError):
        preview_text(payload, SELECTION)


def test_real_sha_capture_reference_collision_remains_concealed():
    selection = (
        SOURCE,
        None,
        None,
        [{"type": "corpus", "version": "v", "key": "698"}],
        "a" * 64,
        None,
    )
    reference = references(selection)[0]
    payload = {"scope": selection[4], "items": [{"reference": reference}]}
    assert "e1e4" in reference
    assert "e1e4" not in preview_text(payload, selection)
