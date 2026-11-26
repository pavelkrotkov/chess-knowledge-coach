"""Prepare one finite corpus window under the capture worker budget."""

from .capture_corpus_coverage import finalize
from .capture_corpus_nomination import build
from .capture_corpus_page import discover
from .capture_corpus_proof import prepare
from .capture_public_page import discover as discover_public
from .capture_public_page import initial


def visit(db, subject, data, progress, check):
    prior = data.get("prior")
    if prior is None:
        return build(db, subject, data, progress, check), 0
    building = prior["building"]
    if building["band"] < 5:
        return discover(db, data, building, check), 0
    building.setdefault("public", initial(subject))
    if not building["public"]["done"]:
        return discover_public(db, subject, data, building, check), 0
    pending = building["pending"]
    if pending:
        entry = prior["entries"][pending[0]]
        pending.append(pending.pop(0))
        used = prepare(db, entry, check)
        if entry["state"] in {"complete", "unresolved", "interrupted"}:
            building["incomplete"] = (
                building.get("incomplete", False) or entry["state"] != "complete"
            )
            pending.pop()
        return True, used
    if building.get("incomplete"):
        data["pending_scope"] = building["scope"]
        data["prior"] = None
        return False, 0
    return finalize(db, data, building, prior)
