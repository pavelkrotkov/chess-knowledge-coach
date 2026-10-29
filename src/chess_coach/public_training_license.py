"""Validate declared source identity and supported redistribution terms."""

import re
from urllib.parse import urlsplit

from .public_training_license_terms import validate_terms

FIELDS = {
    "version",
    "source_url",
    "source_revision",
    "source_sha256",
    "content_sha256",
    "content_format",
    "license",
    "attribution",
    "license_notice",
}


def validate_manifest(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("invalid collection manifest fields")
    _values(value)
    _policy(value)
    for field in ("source_sha256", "content_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", value[field]):
            raise ValueError("invalid collection checksum")


def _policy(value):
    if len(value["version"]) > 120 or len(value["source_revision"]) > 256:
        raise ValueError("invalid collection identity")
    url = urlsplit(value["source_url"])
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise ValueError("source URL must be HTTPS")
    if value["content_format"] not in {"fen_csv", "pgn"}:
        raise ValueError("unsupported collection format")
    validate_terms(value)


def _values(value):
    for field in FIELDS:
        if (
            not isinstance(value[field], str)
            or not value[field].strip()
            or len(value[field]) > 8192
        ):
            raise ValueError("invalid collection manifest value")
