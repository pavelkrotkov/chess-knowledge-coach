"""Expose mastery summaries without private context in worker output."""


def public_report(report: dict) -> dict:
    fields = (
        "skill",
        "operation",
        "status",
        "mastery",
        "uncertainty",
        "effective_weight",
        "trend_30d",
        "context_count",
        "policy_version",
        "as_of",
        "exclusions",
        "supporting_evidence_ids",
    )
    return {key: report[key] for key in fields}
