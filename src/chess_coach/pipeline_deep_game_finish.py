"""Classify interrupted or stale deep execution results."""

import time


def finished(result, report):
    if any(item.get("detail") == "worker_deadline" for item in result["processed"]):
        report["detail"] = "worker_deadline"
        return False
    if any(item["status"] == "stale" for item in result["processed"]):
        report["detail"] = "selection_changed"
        return False
    if result.get("detail"):
        report["detail"] = result["detail"]
        return False
    return True


def interrupted(report, deadline):
    return report.get("detail") == "worker_deadline" or (
        deadline is not None and time.monotonic() >= deadline
    )


def progress(result):
    return sum(
        item["status"] != "stale" and item.get("detail") != "worker_deadline"
        for item in result["processed"]
    )
