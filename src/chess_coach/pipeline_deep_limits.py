"""Summarize normal deep scan capacity and pending work."""


def finish(report, config, games):
    if len(games) > config.deep_max_scan and report["examined"] == config.deep_max_scan:
        report["capped"] = True
    if report["pending"] and report["processed"] >= config.deep_max_jobs:
        report["capped"] = True
    if report["capped"] or report["pending"]:
        report["status"] = "partial"
    return report


def at_capacity(report, config):
    return (
        report["selected_games"] >= config.deep_max_games
        or report["processed"] >= config.deep_max_jobs
    )
