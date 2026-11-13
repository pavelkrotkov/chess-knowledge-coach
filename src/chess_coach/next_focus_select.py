"""Choose among existing qualified families without comparing fork counts."""


# Preserve the established capture/protection order; fork counts use another detector.
def _baseline(capture, protection):
    source = protection and protection["source"]
    if not source:
        return "capture" if capture else None
    if not capture:
        return "protection"
    return "protection" if source["games"] > capture["source"]["games"] else "capture"


def _success(family, capture, assessment, fork):
    if family == "capture":
        history = capture["history"]
        return history["status"] == "correct" and history.get("assistance") == "unassisted"
    if family == "protection":
        return assessment["status"] == "correct"
    return fork["assessment"]["status"] == "correct"


def choose(capture, protection, assessment, fork):
    baseline = _baseline(capture, protection)
    if baseline is None:
        return ("fork", None) if fork else (None, None)
    if not _success(baseline, capture, assessment, fork):
        return baseline, None
    other = "protection" if baseline == "capture" else "capture"
    for family in (other, "fork"):
        if _available(family, capture, protection, fork) and not _success(
            family, capture, assessment, fork
        ):
            return family, baseline
    return baseline, None


def _available(family, capture, protection, fork):
    if family == "capture":
        return bool(capture)
    if family == "protection":
        return bool(protection and protection["source"])
    return bool(fork)
