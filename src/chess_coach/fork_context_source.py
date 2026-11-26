"""Bind a practiced owned fork to its exact retained game root."""

from .curriculum_fork_source import read
from .fact_fingerprint import canonical
from .fork_context_presence import pattern
from .fork_followup_prior import _prior
from .objective_fork_contract import MISS_VERSION
from .objective_fork_source import resolve


def bind(db, subject, corpus, as_of, turns, check):
    candidate, _, report = read(db, subject, corpus, check)
    if candidate is None or report["limited"] or report["assessment"]["status"] != "correct":
        return None
    evidence = candidate["source_evidence_id"]
    source, practice = _prior(
        db, subject, corpus, report["assessment"]["attempt"], check, as_of=as_of
    )
    if source != evidence:
        return None
    snapshot = resolve(db, MISS_VERSION, str(evidence), subject, check=check)
    matched = _match(snapshot, turns)
    if matched is None:
        return None
    turn, root = matched
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    return {"turn": turn, "root": root, "practice": practice, "wanted": (context, pattern(root))}


def _match(snapshot, turns):
    provenance = snapshot["provenance"]
    turn = {row["position_id"]: row for row in turns}[provenance["position_id"]]
    root = {row["move"]: row for row in turn["roots"]}[snapshot["lines"][0]]
    actual = (turn["side"], root["state"], root["targets"])
    expected = (snapshot["learner_color"], "proved", provenance["fork_certificate"]["targets"])
    return (turn, root) if actual == expected else None
