"""Validate the bounded tactical preview contract before source verification."""

from .course_preview import preview_hash
from .tactical_course import CONTRACTS
from .tactical_course_patterns import MAX_PATTERNS
from .tactical_export_selection import selection


def _bounds(body):
    patterns, chapters = body.get("patterns"), body.get("chapters")
    if not isinstance(patterns, list) or not 1 <= len(patterns) <= MAX_PATTERNS:
        raise ValueError("unsupported pattern count")
    if not isinstance(chapters, list) or not len(patterns) <= len(chapters) <= 2 * len(patterns):
        raise ValueError("unsupported chapter count")


def validate(envelope, corpus):
    if not isinstance(envelope, dict) or envelope.get("kind") not in CONTRACTS:
        raise ValueError("unsupported preview")
    body = envelope.get("preview")
    if not isinstance(body, dict) or body.get("kind") != envelope["kind"]:
        raise ValueError("unsupported preview")
    if envelope.get("preview_sha256") != preview_hash(body):
        raise ValueError("preview hash mismatch")
    _bounds(body)
    selection(body, corpus)
    return body


def contract(body):
    version = body["kind"].rsplit("-v", 1)[1]
    return f"local-tactical-course-export-v{version}", f"tactical-export-verification-v{version}"
