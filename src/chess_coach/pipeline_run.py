"""Run ordinary bounded pipeline stages."""

from .fork_defense_worker import process_defenses
from .fork_worker import process_forks
from .material_worker import process_material
from .pipeline_deep_arbitration import attach_status, process_deep_cycle
from .pipeline_inputs import engine_identity
from .pipeline_ordinary import process_ordinary
from .pipeline_sync import sync_result
from .pipeline_worker_report import worker_report


def run_pipeline(db, config, token, transport, clock, phase):
    phase["name"] = "sync"
    sync = sync_result(db, config, token, transport, clock)
    if sync.get("detail") == "worker_process_required":
        return {"status": "failed", "sync": sync, "games": [], "mastery": []}
    phase["name"] = "ordinary"
    engine_hash = engine_identity(config.engine_path)
    games, scan, recent = process_ordinary(db, config, engine_hash)
    phase["name"] = "deep"
    deep, purpose = process_deep_cycle(db, config)
    phase["name"] = "material"
    material = process_material(db, config, engine_hash)
    phase["name"] = "forks"
    forks = process_forks(db, config)
    phase["name"] = "fork_defenses"
    defenses = process_defenses(db, config)
    phase["name"] = "report"
    report = worker_report(db, config, sync, scan, games, deep, material, forks, defenses)
    report["recent_analysis"] = recent
    return attach_status(report, purpose)
