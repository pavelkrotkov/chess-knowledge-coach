"""Bind one admitted capture witness to its exact retained game root."""

from operator import itemgetter

from .capture_compare_signature import projections
from .capture_context_presence import pattern
from .curriculum_capture_practice import evidence
from .fact_fingerprint import canonical
from .fork_followup_first import first


def _match(snapshot, position, observation, turns):
    turn = {item["position_id"]: item for item in turns}[position]
    root = {item["move"]: item for item in turn["roots"]}[snapshot["lines"][0]]
    shape = {key: root["features"][key] for key in ("mover", "target", "geometry")}
    actual = (
        turn["side"],
        root["target_square"],
        root["state"],
        root["mechanism"],
        canonical(shape),
    )
    expected = (
        observation["side"],
        snapshot["provenance"]["objective_target"],
        "proved",
        "direct",
        canonical(observation["pattern"]),
    )
    return (turn, root) if actual == expected else None


def bind(db, subject, corpus, as_of, option, turns, check, *, observed=None):
    _, report = option
    position = report["source"]["position_id"]
    if report["limited"]:
        return None
    if observed is None:
        observed = evidence(db, subject, corpus, position, report["history"], as_of, check)
    if observed is None:
        return None
    observed["controls"], observed["pattern"] = projections(observed["practice_context"], corpus)
    snapshot = report["snapshot"]
    provenance = snapshot["provenance"]
    identity = itemgetter("evidence_id", "source_fingerprint", "review_event_id")
    if (provenance["position_id"], snapshot["learner_color"], identity(provenance)) != (
        position,
        observed["side"],
        identity(observed["binding"]),
    ):
        return None
    try:
        first(db, subject, observed["session"])
        matched = _match(snapshot, position, observed, turns)
    except (ValueError, KeyError):
        return None
    check()
    if matched is None:
        return None
    turn, root = matched
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    return {
        "turn": turn,
        "root": root,
        "practice": {"result": observed["result"], "controls": observed["controls"]},
        "common_practice": {
            "attempt": observed["session"]["attempt_id"],
            "content_key": observed["session"]["source_key"],
            "context": observed["practice_context"],
            "binding": observed["binding"],
        },
        "wanted": (context, pattern(root)),
    }
