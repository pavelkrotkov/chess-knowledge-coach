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
    if "fork_sample" in payload:
        result["fork_sample"] = payload["fork_sample"]
    if legacy is not None:
        result["legacy_capture"] = legacy["branches"]
    return result
