"""Record the exact tactical positions about to be sent in the existing intent."""

import json
from datetime import UTC, datetime

from .fact_fingerprint import digest
from .opening_queue_files import MAX_BYTES
from .study_remote import StudyError
from .tactical_exposure_pgn import positions as pgn_positions


def begin(state, index, chapter):
    delivery = state.get("tactical_delivery")
    if delivery is None:
        return
    positions = sorted(digest(key) for key in pgn_positions(chapter["pgn"]))
    entry = {
        "chapter_hash": digest(chapter["pgn"]),
        "positions": positions,
        "pending_at": datetime.now(UTC).isoformat(),
        "verified_at": None,
    }
    part = delivery.get("multipart")
    if part is not None:
        entry["parent_sha256"] = part["parent_sha256"]
        entry["original_index"] = part["indices"][index]
    delivery["chapters"][str(index)] = entry
    if len(json.dumps(state, sort_keys=True).encode("utf-8")) > MAX_BYTES:
        raise StudyError("tactical exposure intent exceeds limit")
