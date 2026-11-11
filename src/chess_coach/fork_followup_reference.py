"""Bind a matched fork reference to its candidate, prior and frozen cohort."""

import hmac

from .fact_fingerprint import canonical, digest
from .related_mate_search_token import fingerprint


def seal(secret, reference, attempt, context):
    return fingerprint(secret, "fork-followup-reference-v1", [reference, attempt, context])


def seal_result(secret, result, attempt, context):
    if result is not None:
        candidate = result["items"][0]
        candidate["reference"] = seal(secret, candidate["reference"], attempt, context)
    return result


def resolve(selected, secret, reference, attempt, context):
    scope = selected[4]
    for item in selected[3]:
        identity = [scope, item["type"], item["version"], item["key"]]
        ordinary = fingerprint(secret, "capture-reference", identity)
        if hmac.compare_digest(
            seal(secret, ordinary, attempt, context).encode(), reference.encode()
        ):
            return digest(canonical(identity))
    raise ValueError("fork comparison reference changed")
