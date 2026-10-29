"""Check all transfer content except independently verified opaque digest values."""

import copy
import json
import re

from tests.transfer_expected_support import references


def _mask(mapping, field, expected):
    actual = mapping[field]
    if not isinstance(actual, str) or not re.fullmatch(r"[0-9a-f]{64}", actual):
        raise AssertionError("invalid digest")
    if actual != expected:
        raise AssertionError("digest does not match independently selected source")
    mapping[field] = "[opaque]"


def preview_text(payload, selection):
    data = copy.deepcopy(payload)
    _mask(data, "scope", selection[4])
    expected = references(selection)
    if len(data["items"]) > len(expected):
        raise AssertionError("unexpected transfer candidates")
    for item, reference in zip(data["items"], expected, strict=False):
        _mask(item, "reference", reference)
    return json.dumps(data, sort_keys=True)


def binding_text(binding, expected):
    data = copy.deepcopy(binding)
    if set(expected) not in (
        {"source_fingerprint", "source_snapshot_hash"},
        {"source_fingerprint", "source_snapshot_hash", "source_lines_hash"},
    ):
        raise AssertionError("unexpected binding digest fields")
    for field, value in expected.items():
        _mask(data, field, value)
    return json.dumps(data, sort_keys=True)
