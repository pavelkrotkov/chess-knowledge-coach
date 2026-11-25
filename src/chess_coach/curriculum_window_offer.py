"""Sign and recheck one new plan item within its owner-bound window."""

from .curriculum_prerequisite_token import encode
from .curriculum_window_scope import POLICY


def identity(item):
    source = item.get("source_type")
    if item.get("unified_training") and source in {"own-game", "public"}:
        return source, item["source_version"], item["source_key"], "unified"
    mode = "unified" if item.get("unified_training") else "legacy"
    return "corpus", item["corpus_version"], item["puzzle_id"], mode


def issue(db, value, item):
    source, version, key, mode = identity(item)
    return encode(
        db,
        [
            POLICY,
            value["state"]["subject_hash"],
            value["goal"],
            value["expires_at"],
            source,
            version,
            key,
            value["state"]["revision"],
            mode,
        ],
    )
