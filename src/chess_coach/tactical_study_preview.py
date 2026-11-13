"""Recover and hash-check the exact preview embedded in an export."""

import re

from .course_preview import preview_hash
from .tactical_course import (
    LEGACY_POLICY,
    LEGACY_VERSION,
    POLICY,
    PREVIOUS_POLICY,
    PREVIOUS_VERSION,
    PROTECTION_POLICY,
    PROTECTION_VERSION,
    VERSION,
)
from .tactical_export import LEGACY_VERSION as LEGACY_EXPORT_VERSION
from .tactical_export import PREVIOUS_VERSION as PREVIOUS_EXPORT_VERSION
from .tactical_export import PROTECTION_VERSION as PROTECTION_EXPORT_VERSION
from .tactical_export import VERSION as EXPORT_VERSION


def preview(envelope, expected):
    contracts = {
        LEGACY_EXPORT_VERSION: (LEGACY_VERSION, LEGACY_POLICY),
        PREVIOUS_EXPORT_VERSION: (PREVIOUS_VERSION, PREVIOUS_POLICY),
        PROTECTION_EXPORT_VERSION: (PROTECTION_VERSION, PROTECTION_POLICY),
        EXPORT_VERSION: (VERSION, POLICY),
    }
    contract = contracts.get(envelope.get("kind"))
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or contract is None:
        raise ValueError("unsupported tactical export")
    body = envelope["export"]
    if envelope.get("export_sha256") != expected or preview_hash(body) != expected:
        raise ValueError("tactical export hash differs")
    preview = {
        "kind": contract[0],
        "policy": contract[1],
        **{key: body[key] for key in ("selection", "patterns", "chapters")},
    }
    if preview_hash(preview) != body["preview_sha256"]:
        raise ValueError("tactical preview hash differs")
    return {"kind": contract[0], "preview": preview, "preview_sha256": body["preview_sha256"]}
