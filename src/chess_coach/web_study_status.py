"""Expose only a completely verified private Study link."""

import json
import re
from pathlib import Path


def status(root):
    if not root:
        return None
    path = Path(root) / ".runtime" / "planning" / "poc-study-336-intent.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        identifier = state.get("study")
        verified = state.get("verified_at")
        if (
            state.get("complete") is True
            and isinstance(verified, str)
            and re.fullmatch(r"[A-Za-z0-9]{8}", identifier or "")
        ):
            return {"url": "https://lichess.org/study/" + identifier, "verified_at": verified}
    except (OSError, ValueError, TypeError):
        pass
    return None
