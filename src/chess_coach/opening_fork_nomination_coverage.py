"""Describe whether the selected public cohort was fully checked."""


def _analyzed(forks):
    selected = forks.get("selected")
    return (
        type(selected) is int
        and selected > 0
        and selected == forks.get("attempted") == forks.get("analyzed")
    )


def complete(sample, cohort, forks):
    if not isinstance(sample, dict):
        return False
    flags = (sample.get("truncated"), cohort.get("more_eligible"), forks.get("interrupted"))
    counts = (
        cohort.get("unknown_context"),
        forks.get("unsupported"),
        forks.get("incomplete"),
        forks.get("censored"),
    )
    return (
        all(value is False for value in flags)
        and all(type(value) is int and value == 0 for value in counts)
        and _analyzed(forks)
    )


def coverage(proof, played, forks):
    cohort = forks if "eligible" in forks else played
    sample = (
        proof.get("fork_sample") if proof["fork_window"] == "continuation" else proof.get("sample")
    )
    return {
        "coverage_complete": complete(sample, cohort, forks),
        "sample_truncated": sample.get("truncated") if isinstance(sample, dict) else None,
        "more_eligible": cohort.get("more_eligible"),
        "unknown_context": cohort.get("unknown_context"),
    }
