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
    if "prevention" in payload["binding"]["policy"]:
        policy = payload["binding"]["policy"]
        result["prevention_policy"] = {
            **policy["prevention"],
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
    if kind == "prevention":
        result["prevention_status"] = "prepared" if "prevention_policy" in result else "unavailable"
    return result
