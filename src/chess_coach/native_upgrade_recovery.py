"""Revalidate a retained standalone recovery against the pinned source."""

from .native_upgrade_archive import verify as verify_archive
from .native_upgrade_integrity import verify as verify_integrity
from .native_upgrade_recovery_paths import paths as recovery_paths
from .native_upgrade_recovery_paths import stable
from .recovery_codec import routines
from .recovery_copy import pinned
from .recovery_fidelity import verify_fidelity
from .recovery_gzip_files import digest_file
from .recovery_gzip_manifest import load, verify_metadata
from .recovery_paths import ensure_no_companions
from .recovery_verify import require_standalone, verify_database


def verify(connection, root, source, archive, restored, deadline, *, codec):
    source, archive, restored = recovery_paths(root, source, archive, restored)
    manifest_path = archive.with_name(archive.name + ".manifest.json")
    paths = (source, archive, restored, manifest_path)
    before = [
        (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        for s in (path.stat() for path in paths)
    ]
    _, _, validator = routines(codec)
    manifest = load(archive, validator=validator)
    if manifest["user_version"] != 32:
        raise ValueError("recovery version differs")
    if digest_file(archive, deadline) != manifest["archive_sha256"]:
        raise ValueError("recovery archive differs")
    if digest_file(restored, deadline) != manifest["raw_sha256"]:
        raise ValueError("recovery restore differs")
    verify_archive(archive, manifest, deadline, codec)
    require_standalone(restored)
    verify_integrity(connection)
    previous_factory = connection.text_factory
    try:
        with pinned(restored, deadline, require_memory=True) as backup:
            backup.execute("PRAGMA query_only=ON")
            verify_metadata(backup, manifest)
            verify_database(backup)
            verify_fidelity(connection, backup, deadline)
    finally:
        connection.text_factory = previous_factory
    stable(paths, before)
    ensure_no_companions(source)
    ensure_no_companions(restored)
