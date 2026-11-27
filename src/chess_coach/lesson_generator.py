"""Allow a trusted generator to order verified examples, never invent claims."""

from copy import deepcopy

from .lesson_order import order as validated_order

PROMPT_VERSION = "lesson-order-v1"


def generate(db, lesson, generator, *, model):
    """Use only a complete permutation; unsupported output falls back silently."""
    examples = lesson["examples"]
    inputs = {
        "lesson": deepcopy(lesson),
        "allowed_output": "JSON object with order as a permutation of example indices",
    }
    provenance = {"attempted_model": model, "prompt_version": PROMPT_VERSION, "input": inputs}
    if generator is None:
        return lesson, {**provenance, "status": "not_requested"}
    if not examples or not model or db.connection.in_transaction:
        return lesson, {**provenance, "status": "fallback"}
    try:
        response = generator({"facts": deepcopy(inputs)})
        order = validated_order(response, len(examples))
    except Exception:
        order = None
    if order is None:
        return lesson, {**provenance, "status": "fallback"}
    revised = {**lesson, "examples": [examples[i] for i in order]}
    return revised, {**provenance, "status": "validated"}
