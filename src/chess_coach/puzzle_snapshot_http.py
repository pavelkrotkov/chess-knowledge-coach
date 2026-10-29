"""Validate source identity and HTTP response semantics."""

import re


def strong_etag(value):
    return bool(value and re.fullmatch(r'"[^"\\\x00-\x1f\x7f]*"', value))


def _length(headers):
    value = headers.get("content-length", "")
    if not value.isdecimal() or int(value) <= 0:
        raise ValueError("missing or invalid Content-Length")
    return int(value)


def validate_response(response, state, offset):
    if offset:
        total = state["expected_bytes"]
        expected = f"bytes {offset}-{total - 1}/{total}"
        if response.status_code != 206 or response.headers.get("content-range") != expected:
            raise ValueError("source changed or range response did not match")
        if response.headers.get("etag") != state["etag"]:
            raise ValueError("source validator changed")
        if _length(response.headers) != state["expected_bytes"] - offset:
            raise ValueError("range length did not match")
    else:
        if response.status_code != 200:
            raise ValueError(f"provider returned HTTP {response.status_code}")
        state["expected_bytes"] = _length(response.headers)
        etag = response.headers.get("etag")
        state["etag"] = etag if strong_etag(etag) else None


def request_headers(state, offset):
    if offset:
        return {
            "Range": f"bytes={offset}-",
            "If-Range": state["etag"],
            "Accept-Encoding": "identity",
        }
    return {"Accept-Encoding": "identity"}
