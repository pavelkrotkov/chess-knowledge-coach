"""Create a gzip backup and verify one separate SQLite restore."""

from pathlib import Path

from .recovery_capacity import MIN_WORKING
from .recovery_deadline import Deadline
from .recovery_gzip_capacity import estimate, pinned_plan
from .recovery_gzip_execute import create
from .recovery_gzip_snapshot import _companions, pinned_raw
from .recovery_paths import recovery_paths
from .recovery_physical import physical
from .recovery_verify import require_standalone


def compressed_recovery(source, archive, restored, *, project_root, check_only=False):
    """Back up a pinned DELETE database and verify an independent restore."""
    source, archive, restored, manifest, root = _paths(source, archive, restored, project_root)
    deadline = Deadline()
    _companions(source)
    require_standalone(source)
    physical_report = physical(source, root, archive, deadline, working_bytes=MIN_WORKING)
    report = estimate(physical_report["estimated_snapshot_bytes"], root, archive, deadline)
    if physical_report["status"] != "fits":
        report["status"] = physical_report["status"]
    if check_only:
        return report
    if report["status"] != "conditional":
        raise ValueError("recovery capacity unavailable; no destination was created")
    with pinned_raw(source, deadline) as (reader, raw, metadata):
        report = pinned_plan(reader, root, archive, deadline)
        if report["status"] != "conditional":
            raise ValueError("recovery capacity unavailable; no destination was created")
        return create(reader, raw, metadata, root, (archive, restored, manifest), report, deadline)


def _paths(source, archive, restored, project_root):
    root = Path(project_root).resolve(strict=True)
    source, archive = recovery_paths(source, archive, root)
    _, restored = recovery_paths(source, restored, root)
    _, manifest = recovery_paths(source, str(archive) + ".manifest.json", root)
    if len({source, archive, restored, manifest}) != 4:
        raise ValueError("recovery paths must be distinct")
    if archive.parent.stat().st_dev != restored.parent.stat().st_dev:
        raise ValueError("compressed backup and restore must share a filesystem")
    return source, archive, restored, manifest, root
