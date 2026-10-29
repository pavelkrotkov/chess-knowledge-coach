"""Inspect fork pages while masking only independently verified opaque inputs."""

import re

from tests.test_unified_sessions import token


def without_opaque_inputs(body, csrf, reference=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", csrf):
        raise AssertionError("invalid session CSRF token")
    result = _mask_input(body, "csrf", csrf)
    if reference is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", reference):
            raise AssertionError("invalid source reference")
        result = _mask_input(result, "reference", reference)
    return result


def _mask_input(body, name, value):
    field = f'<input type="hidden" name="{name}" value="{value}">'.encode()
    if field not in body:
        raise AssertionError("expected opaque input missing or changed")
    return body.replace(field, f'<input type="hidden" name="{name}" value="[opaque]">'.encode())


def assert_concealed(page, csrf, reference=None, *, answer=b"b5c7"):
    assert page.status_code == 200
    assert token(page, "csrf") == csrf
    if reference is not None:
        assert token(page, "reference") == reference
    assert answer not in without_opaque_inputs(page.data, csrf, reference)


def assert_collision(page, collision, *, answer=b"b5c7"):
    if collision != "none":
        assert answer in page.data
