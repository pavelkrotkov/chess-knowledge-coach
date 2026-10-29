"""Expose mastery summaries without private context in worker output."""

from .mastery import mastery_report
from .pipeline_deep_config import combined_status
from .pipeline_health import run_status


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


def pipeline_report(db, config, sync, scan, games, deep, material, forks):
    reports = mastery_report(db, subject=config.learner)
    status = combined_status(
        combined_status(combined_status(run_status(db, sync, games, scan), deep), material), forks
    )
    return {
        "status": status,
        "sync": sync,
        "scan": scan,
        "deep": deep,
        "material": material,
        "forks": forks,
        "games": games,
        "mastery": [public_report(row) for row in reports],
    }
