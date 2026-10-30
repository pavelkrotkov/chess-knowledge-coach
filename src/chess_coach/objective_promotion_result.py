"""Classify and bound an exhaustive promotion proof."""

import json

from .objective_capture_proof import unknown


def classify(proof, base, nodes, clock, start, seconds):
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if len(json.dumps(proof, sort_keys=True).encode()) > 65536:
        return unknown(base, "proof_size_limit")
    status = {"proved": "correct", "disproved": "incorrect", "unknown": "unresolved"}[
        proof["status"]
    ]
    return {
        **base,
        "status": status,
        "reason": proof.get("reason", "forced_promotion_proved"),
        "proof": proof,
        "nodes": nodes,
    }
