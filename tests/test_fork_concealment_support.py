"""Opaque test inputs never hide meaningful fork solution content."""

import pytest

from tests.fork_concealment_support import without_opaque_inputs

CSRF = "b5c7" + "A" * 39
REFERENCE = "b5c7" + "a" * 60
BODY = (
    f'<input type="hidden" name="csrf" value="{CSRF}">'
    f'<input type="hidden" name="reference" value="{REFERENCE}">'
).encode()


def test_expected_opaque_fields_can_contain_move_characters():
    assert b"b5c7" in BODY
    assert b"b5c7" not in without_opaque_inputs(BODY, CSRF, REFERENCE)


@pytest.mark.parametrize(
    "injected",
    [
        b"<p>b5c7</p>",
        b'<div data-answer="b5c7"></div>',
        b'<input type="hidden" name="other" value="b5c7">',
        b'<input type="hidden" name="reference" value="b5c7-invalid">',
    ],
)
def test_nonopaque_solution_text_is_still_detected(injected):
    assert b"b5c7" in without_opaque_inputs(BODY + injected, CSRF, REFERENCE)


@pytest.mark.parametrize(
    "csrf,reference",
    [(CSRF, "b5c7-invalid"), ("invalid-b5c7", REFERENCE), (CSRF, "a" * 64)],
)
def test_invalid_or_changed_expected_values_are_not_ignored(csrf, reference):
    with pytest.raises(AssertionError):
        without_opaque_inputs(BODY, csrf, reference)
