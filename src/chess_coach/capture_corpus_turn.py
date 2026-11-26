"""Admit and advance a prepared corpus window in a shared worker turn."""

from .capture_certificate_refresh import check
from .capture_corpus_storage import _valid, open_turn, publish
from .capture_corpus_worker import visit as corpus_visit
from .fact_fingerprint import canonical
from .short_mate_trend_store import read


def visit(db, subject, root, current, deadline):
    prepared = current["_prepared"]
    if not prepared:
        path, pool = open_turn(db, root, deadline)
        if pool is None:
            return False, 0
        prepared.update(path=path, pool=pool, before=canonical(pool))
    return corpus_visit(db, subject, prepared["pool"], current["corpus"], lambda: check(deadline))


def finish(prepared):
    if prepared and canonical(prepared["pool"]) != prepared["before"]:
        publish(prepared["path"], prepared["pool"], prepared["before"])
        actual = read(prepared["path"], prepared["pool"]["policy"], validator=_valid)
        return actual is not None and canonical(actual) == canonical(prepared["pool"])
    return False
