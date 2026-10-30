"""Rebind a purpose comparison to its separately recorded original proof."""

import json

from .fact_fingerprint import canonical
from .style_protection_collect import collect
from .style_protection_purpose_cache import source


def inspect(db, learner, context, board, compared, allocation, budget, history, cache, duplicate):
    try:
        found, reason = source(db, learner, context, board, budget, history, cache)
        if found is None:
            return None, reason
        evidence, proof, actual = found
        if actual != canonical(json.loads(allocation["binding_json"])):
            return None, "original_source_changed"
        if duplicate:
            return {}, "duplicate"
        results = collect(
            db, learner, context, board, compared, evidence, budget, source=proof, history=history
        )
        return results, "current" if results is not None else "source_or_proof_unavailable"
    except (ValueError, TypeError, KeyError, IndexError):
        return None, "source_or_proof_unavailable"
