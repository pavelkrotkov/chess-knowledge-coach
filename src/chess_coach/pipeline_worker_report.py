"""Run bounded endgame workers and extend the existing pipeline report."""

from .discovery_pipeline import process_discoveries
from .king_safety_worker import process_king_safety_lessons
from .mate_worker import process_mates
from .objective_worker import process as process_objectives
from .pawn_coach_worker import process_pawns
from .pawn_structure_worker import process_structure_lessons
from .pin_worker import process_pins
from .pipeline_deep_config import combined_status
from .pipeline_report import pipeline_report
from .rook_plan_worker import process_rook_plans


def worker_report(db, config, sync, scan, games, deep, material, forks, defenses):
    discoveries = process_discoveries(db, config)
    objectives = process_objectives(db, config.learner, limit=4)
    structures = process_structure_lessons(db, config)
    rooks = process_rook_plans(db, config)
    king_safety = process_king_safety_lessons(db, config)
    mate = process_mates(db, config)
    pawns = process_pawns(db, config)
    result = pipeline_report(db, config, sync, scan, games, deep, material, forks, defenses, pawns)
    result["status"] = combined_status(result["status"], mate)
    result["status"] = combined_status(result["status"], structures)
    result["status"] = combined_status(result["status"], rooks)
    result["rook_plans"] = rooks
    result["status"] = combined_status(result["status"], king_safety)
    result["king_safety_lessons"] = king_safety
    result["pawn_structure_lessons"] = structures
    for operation in ("execute", "prevent"):
        pins = process_pins(db, config, operation)
        result["status"] = combined_status(result["status"], pins)
        result[f"pin_{operation}"] = pins
    result["status"] = combined_status(result["status"], discoveries)
    result["discoveries"] = discoveries
    result["status"] = combined_status(result["status"], objectives)
    result["objective_verification"] = objectives
    result["mate"] = mate
    return result
