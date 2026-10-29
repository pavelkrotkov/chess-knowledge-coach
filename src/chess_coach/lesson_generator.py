"""Allow a trusted generator to order verified examples, never invent claims."""

from .enrichment import explain_position
from .lesson_order import order as validated_order

PROMPT_VERSION = "lesson-order-v1"


def generate(db, lesson, generator, *, model):
    """Use only a complete permutation; unsupported output falls back silently."""
    examples = lesson["examples"]
    inputs = {
        "lesson": lesson,
        "allowed_output": "JSON object with order as a permutation of example indices",
    }
    provenance = {"attempted_model": model, "prompt_version": PROMPT_VERSION, "input": inputs}
    if not examples or not model or db.connection.in_transaction:
        return lesson, {**provenance, "status": "fallback"}
    try:
        response = generator({"facts": inputs})
        order = validated_order(response, len(examples))
    except Exception:
        order = None
    if order is None:
        return lesson, {**provenance, "status": "fallback"}
    position_id = examples[0]["position_id"]
    explain_position(
        db,
        position_id,
        facts=inputs,
        generator=lambda _: response,
        model=model,
        prompt_version=PROMPT_VERSION,
    )
    revised = {**lesson, "examples": [examples[i] for i in order]}
    return revised, {**provenance, "status": "validated"}
