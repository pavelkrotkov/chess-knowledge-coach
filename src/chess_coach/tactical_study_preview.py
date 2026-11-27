"""Recover and hash-check the exact preview embedded in an export."""

import re

from .course_preview import preview_hash
from .tactical_course import (
    DEFAULT_ROLES_POLICY,
    DEFAULT_ROLES_VERSION,
    LEGACY_POLICY,
    LEGACY_VERSION,
    NAMED_POLICY,
    NAMED_VERSION,
    POLICY,
    PREVIOUS_POLICY,
    PREVIOUS_VERSION,
    PROTECTION_POLICY,
    PROTECTION_VERSION,
    SELECTED_FORK_POLICY,
    SELECTED_FORK_VERSION,
    SELECTED_POLICY,
    SELECTED_ROLES_POLICY,
    SELECTED_ROLES_VERSION,
    SELECTED_VERSION,
    THEMATIC_POLICY,
    THEMATIC_SELECTED_POLICY,
    THEMATIC_SELECTED_VERSION,
    THEMATIC_VERSION,
    VERSION,
)
from .tactical_export import LEGACY_VERSION as LEGACY_EXPORT_VERSION
from .tactical_export import PREVIOUS_VERSION as PREVIOUS_EXPORT_VERSION
from .tactical_export import PROTECTION_VERSION as PROTECTION_EXPORT_VERSION
from .tactical_export import SELECTED_VERSION as SELECTED_EXPORT_VERSION
from .tactical_export import THEMATIC_EXPORT_VERSION, THEMATIC_SELECTED_EXPORT_VERSION
from .tactical_export import VERSION as EXPORT_VERSION


def preview(envelope, expected):
    contracts = {
        LEGACY_EXPORT_VERSION: (LEGACY_VERSION, LEGACY_POLICY),
        PREVIOUS_EXPORT_VERSION: (PREVIOUS_VERSION, PREVIOUS_POLICY),
        PROTECTION_EXPORT_VERSION: (PROTECTION_VERSION, PROTECTION_POLICY),
        EXPORT_VERSION: (VERSION, POLICY),
        SELECTED_EXPORT_VERSION: (SELECTED_VERSION, SELECTED_POLICY),
        THEMATIC_EXPORT_VERSION: (THEMATIC_VERSION, THEMATIC_POLICY),
        THEMATIC_SELECTED_EXPORT_VERSION: (THEMATIC_SELECTED_VERSION, THEMATIC_SELECTED_POLICY),
        "local-tactical-course-export-v8": (NAMED_VERSION, NAMED_POLICY),
        "local-tactical-course-export-v9": (DEFAULT_ROLES_VERSION, DEFAULT_ROLES_POLICY),
        "local-tactical-course-export-v10": (SELECTED_ROLES_VERSION, SELECTED_ROLES_POLICY),
        "local-tactical-course-export-v11": (SELECTED_FORK_VERSION, SELECTED_FORK_POLICY),
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
