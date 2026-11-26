"""Private bounded storage for prepared corpus windows."""

import json
import subprocess
from contextlib import suppress

from .capture_game_trend_paths import location as trend_location
from .fact_fingerprint import canonical, digest
from .material_capture_gain import MIN_GAIN
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .material_reply_guard import MAX_REPLIES
from .material_reply_guard import MIN_GAIN as REPLY_GAIN
from .material_values import VALUES
from .objective_capture_judge import VERSION as JUDGE_VERSION
from .opening_recent_capacity import check as capacity
from .puzzle_session_validate import CORPUS_PLIES_LIMIT
from .related_capture_assessment import HISTORY, SECONDS
from .related_capture_assessment import VERSION as ASSESSMENT_VERSION
from .short_mate_trend_paths import source_identity
from .short_mate_trend_store import MAX_BYTES, read
from .short_mate_trend_store import write as write_pool

POLICY = (
    "related-capture-pool-v1",
    ASSESSMENT_VERSION,
    JUDGE_VERSION,
    HISTORY,
    MIN_GAIN,
    MAX_EXCHANGE_NODES,
    MAX_EXCHANGE_PLIES,
    MAX_REPLIES,
    REPLY_GAIN,
    SECONDS,
    CORPUS_PLIES_LIMIT,
    digest(canonical(VALUES)),
)
LIMIT = 1000


def location(db, root):
    base = trend_location(db, root)
    return base.with_name(db.path.name + ".related-capture-pool.json") if base else None


def _valid(data, expected):
    entries = data.get("entries")
    return (
        data.get("policy") == expected
        and isinstance(entries, dict)
        and len(entries) <= LIMIT
        and all(isinstance(k, str) and isinstance(v, dict) for k, v in entries.items())
    )


def binding(db):
    return [*POLICY, *source_identity(db, "prepared-corpus")]


def load(db, root):
    path = location(db, root)
    return read(path, binding(db), validator=_valid) if path else None


def open_turn(db, root, deadline):
    path = location(db, root)
    if (
        path is None
        or db.connection.execute(
            "SELECT 1 FROM puzzle_corpora WHERE state='ready' LIMIT 1"
        ).fetchone()
        is None
    ):
        return None, None
    try:
        capacity(root, path.parent, deadline=deadline, working=2 * MAX_BYTES + 4096)
    except (OSError, TimeoutError, ValueError, subprocess.SubprocessError):
        return None, None
    pool = load(db, root) or {
        "policy": binding(db),
        "entries": {},
        "prior": None,
        "complete": None,
    }
    return path, pool


def publish(path, pool, previous):
    encoded = canonical({**pool, "checksum": digest(canonical(pool))}).encode()
    if len(encoded) > MAX_BYTES - 512:
        wanted = (pool.get("prior") or {}).get("building") or pool.get("complete") or {}
        pool = json.loads(previous)
        pool.pop("prior", None)
        pool["overflow"] = wanted.get("scope")
    # A too-large fallback leaves the previous complete atomic file untouched.
    with suppress(ValueError):
        write_pool(path, pool)
