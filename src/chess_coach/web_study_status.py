"""Expose a verified private Study link to a useful chapter."""

import json
import re
from pathlib import Path


def status(root):
    try:
        planning = Path(root) / ".runtime" / "planning"
        state = json.loads((planning / "poc-study-336-intent.json").read_text(encoding="utf-8"))
        if state.get("complete") is not True:
            return None
        study = state.get("study")
        receipt = planning / "poc-study-346-presentation.json"
        if receipt.exists():
            presentation = json.loads(receipt.read_text(encoding="utf-8"))
            if presentation.get("study") != study or presentation.get("verified") is not True:
                return None
            chapter = presentation.get("entry_chapter")
            verified = presentation.get("verified_at")
        else:
            chapter = state.get("entry_chapter")
            verified = state.get("verified_at")
        return _link(study, chapter, verified)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _link(study, chapter, verified):
    if not isinstance(verified, str):
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9]{8}", item or "") for item in (study, chapter)):
        return None
    return {"url": f"https://lichess.org/study/{study}/{chapter}#0", "verified_at": verified}
