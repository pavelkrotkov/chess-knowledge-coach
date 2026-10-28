"""Canonical JSON and digests for detector provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("detector data must be finite JSON") from exc


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
