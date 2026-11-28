"""Present immutable public preparation results."""


def view(payload, legacy=None):
    result = {
        "version": payload["version"],
        "status": "prepared",
        "reference": payload["binding"]["reference"],
        "sample": payload["sample"],
        "branches": payload["branches"],
    }
    if "fork" in payload["binding"]["policy"]:
        result["fork_policy"] = payload["binding"]["policy"]["fork"]
    policy = payload["binding"]["policy"]
    for key, label in (
        ("prevention", "prevention"),
        ("protection", "protection"),
        ("defense_pv", "defense"),
        ("mate", "mate"),
        ("short_mate", "short_mate"),
    ):
        if key in policy:
            result[f"{label}_policy"] = {
                **policy[key],
                "proof_seconds": policy["proof_seconds"],
                "shared_seconds": policy["shared_seconds"],
            }
    if "fork_sample" in payload:
        result["fork_sample"] = payload["fork_sample"]
    if legacy is not None:
        result["legacy_capture"] = legacy["branches"]
    return result


def requested(result, window, kind):
    result["fork_window"] = window
    result["proof_kind"] = kind
    if kind in {"protection", "prevention", "mate", "short_mate"}:
        result[f"{kind}_status"] = "prepared" if f"{kind}_policy" in result else "unavailable"
    return result
