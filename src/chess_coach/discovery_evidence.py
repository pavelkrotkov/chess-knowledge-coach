"""Recheck discovery evidence against the current owned decision."""

from functools import partial

from .discovery_contract import MAPPER
from .discovery_evidence_identity import belongs as _belongs
from .discovery_evidence_identity import run_matches as _run_matches
from .discovery_evidence_policy import valid as _valid
from .discovery_observation import observe
from .fork_evidence_current import current_fork
from .fork_evidence_verify import verified_fen


def current(db, evidence, *, _history=None):
    if not _belongs(evidence):
        return None, None, None
    if not _run_matches(db, evidence):
        return {}, "stale", None
    verify = partial(verified_fen, observer=observe)
    result = current_fork(
        db, evidence, mapper=MAPPER, validator=_valid, verify=verify, _history=_history
    )
    if result[1] == "current" and not _run_matches(db, evidence):
        return {}, "stale", None
    return result
