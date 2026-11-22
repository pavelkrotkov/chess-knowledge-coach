"""Bind exact canonical promotion opportunities to recorded-practice context."""

from .curriculum_public_source import prompt_key
from .fact_fingerprint import canonical, digest
from .plan_promotion import _next
from .plan_promotion_catalog import VERSION
from .public_training_source import resolve
from .tactical_exposure_practice import check as exposure
from .unified_source_current import snapshot_hash


def choices(done):
    checked, result = set(done), []
    while len(result) < 4:
        choice = _next(checked)
        if choice is None:
            break
        result.append(choice)
        checked.add(choice[0])
    return result


def candidate(db, subject, choice, context):
    key, color, objective = choice
    snapshot = resolve(db, VERSION, key, verify=False)
    if (snapshot["learner_color"], snapshot["objective"]) != (color, objective):
        raise ValueError("canonical source changed")
    prompt = prompt_key(snapshot["prompt_fen"])
    history = exposure(db, subject, prompt)
    if history not in {"clear", "history_unknown"}:
        return None, "provided" if history == "provided" else "exposure_unknown"
    fingerprint = snapshot_hash(snapshot)
    binding = digest(canonical([VERSION, key, fingerprint, prompt, context["scope"], history]))
    source = snapshot["provenance"]
    reason = (
        "Continue your recorded promotion practice."
        if context["state"] == "continuation"
        else "Optional first recorded practice with these curated promotion positions. Earlier practice isn't known."
    )
    if history == "history_unknown":
        reason += " Earlier coach delivery is unknown."
    reason += " This does not establish a win or mastery."
    return {
        "kind": "new",
        "item_id": None,
        "due": None,
        "source_type": "public",
        "source_version": VERSION,
        "source_key": key,
        "prompt_fen": snapshot["prompt_fen"],
        "prompt_key": prompt,
        "skill": "promotion",
        "operation": "execute",
        "objective": "Complete the stated promotion objective.",
        "reason": reason,
        "source_attribution": source["attribution"],
        "source_license": source["license"],
        "source_snapshot_hash": fingerprint,
        "exposure_state": history,
        "unified_training": True,
        "binding": binding,
    }, "available"
