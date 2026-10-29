"""Run bounded endgame workers and extend the existing pipeline report."""

from .mate_worker import process_mates
from .pawn_coach_worker import process_pawns
from .pipeline_deep_config import combined_status
from .pipeline_report import pipeline_report


def worker_report(db, config, sync, scan, games, deep, material, forks, defenses):
    mate = process_mates(db, config)
    pawns = process_pawns(db, config)
    result = pipeline_report(db, config, sync, scan, games, deep, material, forks, defenses, pawns)
    result["status"] = combined_status(result["status"], mate)
    result["mate"] = mate
    return result
