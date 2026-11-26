"""Resolve the already enumerated bounded owned-capture witnesses."""

from .capture_plan_history import latest
from .curriculum_capture_source import _candidate
from .curriculum_capture_source_identity import collect
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_source import resolve
from .unified_sources import resolve_source


def _resolve(db, subject, corpus, source, limited, scanned, check):
    history = latest(db, subject, source["position_id"], corpus, check=check)
    if history.get("status") in {"stale", "pending", "incomplete"}:
        raise ValueError("capture history unavailable")
    report = {"source": source, "history": history, "limited": limited, "scanned": scanned}
    resolve_source(db, "own-game", source["version"], source["key"], subject=subject, check=check)
    key = str(source["evidence_id"])
    value = resolve(db, TARGET_VERSION, key, subject, check=check)
    check()
    return _candidate(report, value, key), report


def candidates(db, subject, corpus, check):
    """Resolve at most two source witnesses once under the caller's budget."""
    sources, limited, scanned, identity = collect(db, subject, check)
    found = [_resolve(db, subject, corpus, source, limited, scanned, check) for source in sources]
    return found, "available" if found else "no_source", identity
