"""Resolve the already enumerated bounded owned-capture witnesses."""

from .capture_plan_history import latest
from .curriculum_capture_source import _candidate
from .curriculum_capture_source_identity import collect
from .fact_fingerprint import canonical, digest
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_source import resolve
from .unified_sources import resolve_source


def _resolve(db, subject, corpus, source, limited, scanned, check, include_snapshot):
    history = latest(db, subject, source["position_id"], corpus, check=check, prove_latest=True)
    report = {"source": source, "history": history, "limited": limited, "scanned": scanned}
    if history.get("status") in {"stale", "pending", "incomplete"}:
        return None, report
    resolve_source(db, "own-game", source["version"], source["key"], subject=subject, check=check)
    key = str(source["evidence_id"])
    value = resolve(db, TARGET_VERSION, key, subject, check=check)
    check()
    if include_snapshot:
        report["snapshot"] = value
    return _candidate(report, value, key), report


def candidates(db, subject, corpus, check, *, include_snapshot=False, limit=2):
    """Resolve at most two source witnesses once under the caller's budget."""
    sources, limited, scanned, identity = collect(db, subject, check, limit=limit)
    found = []
    for source in sources:
        candidate, report = _resolve(
            db, subject, corpus, source, limited, scanned, check, include_snapshot
        )
        if candidate is None:
            return found, "available" if found else "history_unavailable", identity, report
        found.append((candidate, report))
    return found, "available" if found else "no_source", identity, None


def descriptive(db, subject, corpus, check):
    sources, limited, scanned, identity = collect(db, subject, check, limit=2)
    found = []
    for source in sources:
        try:
            value, report = _resolve(db, subject, corpus, source, limited, scanned, check, True)
        except ValueError as error:
            if str(error) not in {
                "practice source unavailable",
                "capture objective unavailable",
                "capture history unavailable",
                "capture source unavailable",
                "capture target unavailable",
            }:
                raise
            check()
            continue
        if value is not None:
            found.append((value, report))
    return found, identity


def pending(identity, options):
    return digest(canonical([identity, [item["binding"] for item, _ in options]]))
