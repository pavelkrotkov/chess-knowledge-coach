"""Recover and hash-check the exact preview embedded in an export."""

import re

from .course_preview import preview_hash
from .tactical_course import VERSION as PREVIEW_VERSION
from .tactical_export import VERSION


def preview(envelope, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or envelope.get("kind") != VERSION:
        raise ValueError("unsupported tactical export")
    body = envelope["export"]
    if envelope.get("export_sha256") != expected or preview_hash(body) != expected:
        raise ValueError("tactical export hash differs")
    preview = {
        "kind": PREVIEW_VERSION,
        "policy": "provisional-recurring-tactics-v1",
        **{key: body[key] for key in ("selection", "patterns", "chapters")},
    }
    if preview_hash(preview) != body["preview_sha256"]:
        raise ValueError("tactical preview hash differs")
    return {"kind": PREVIEW_VERSION, "preview": preview, "preview_sha256": body["preview_sha256"]}
