"""Extend the existing bounded pipeline report with mate coverage."""

from .pipeline_deep_config import combined_status
from .pipeline_report import pipeline_report


def worker_report(db, config, sync, scan, games, deep, material, forks, defenses, mate):
    result = pipeline_report(db, config, sync, scan, games, deep, material, forks, defenses)
    result["status"] = combined_status(result["status"], mate)
    result["mate"] = mate
    return result
