"""Describe the worker-wide reservation for pin-prevention requests."""

from .objective_pin_prevent_contract import OBJECTIVE
from .objective_pin_prevent_limits import CAPTURE_LIMIT, PROOF_LIMIT


def work_limit(rows):
    count = sum(row["objective_version"] == OBJECTIVE for row in rows)
    return (
        {
            "pin_prevention_work_limit": {
                "requests": count,
                "pin_proof_units_cap": count * PROOF_LIMIT,
                "exposure_capture_probe_units_cap": count * CAPTURE_LIMIT,
            }
        }
        if count
        else {}
    )
