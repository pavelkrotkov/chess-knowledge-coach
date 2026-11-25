"""Requalify the actual owned fork and its current exposure."""

from .curriculum_fork_source import read
from .fact_fingerprint import digest
from .opening_context_launch_match import eligible
from .tactical_exposure_practice import check as exposure


def bind(db, subject, current, corpus, data, version, key):
    budget = current["budget"]
    with budget.scope(snapshot=False):
        candidate, _, _ = read(db, subject, corpus, budget.check)
        if candidate is None or eligible(current, [candidate]) is None:
            raise ValueError("opening fork unavailable")
        if (
            candidate["source_version"],
            candidate["source_key"],
            digest(candidate["prompt_key"]),
        ) != (version, key, data[6]):
            raise ValueError("opening fork changed")
        if exposure(db, subject, candidate["prompt_key"]) != data[7]:
            raise ValueError("opening exposure changed")
    return {"prompt": candidate["prompt_key"], "exposure": data[7]}
