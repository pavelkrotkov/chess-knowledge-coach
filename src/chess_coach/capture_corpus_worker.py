"""Prepare one finite corpus window under the capture worker budget."""

from .capture_corpus_coverage import finalize
from .capture_corpus_nomination import build
from .capture_corpus_page import discover
from .capture_corpus_proof import prepare


def visit(db, subject, data, progress, check):
    prior = data.get("prior")
    if prior is None:
        return build(db, subject, data, progress, check), 0
    building = prior["building"]
    if building["band"] < 5:
        return discover(db, data, building, check), 0
    pending = building["pending"]
    if pending:
        entry = prior["entries"][pending[0]]
        pending.append(pending.pop(0))
        if entry["state"] == "interrupted":
            building["incomplete"] = True
            pending.pop()
            return True, 0
        used = _prepare(db, entry, check)
        if entry["state"] in {"complete", "unresolved"}:
            building["incomplete"] = (
                building.get("incomplete", False) or entry["state"] == "unresolved"
            )
            pending.pop()
        return True, used
    if building.get("incomplete"):
        data["pending_scope"] = building["scope"]
        data["prior"] = None
        return False, 0
    return finalize(db, data, building, prior)


def _prepare(db, entry, check):
    if entry["candidate"]["type"] != "public":
        return prepare(db, entry, check)
    from .capture_public_proof import qualify

    try:
        return qualify(db, entry, check)
    except TimeoutError:
        entry["state"] = "interrupted"
        raise
