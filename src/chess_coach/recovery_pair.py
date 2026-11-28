"""Explicit offline archive-pair recovery with a leased raw source."""

import os

from .recovery_deadline import Deadline
from .recovery_pair_lease import Lease
from .recovery_pair_metadata import write as write_metadata
from .recovery_pair_prepare import create_pair, paths
from .recovery_pair_restore import restore_pair
from .recovery_pair_space import require_space
from .recovery_pair_stream import compare, raw_digest

SECONDS = 3600


def _prove_pair(lease, a, b, metadata, first, second, deadline):
    with os.fdopen(lease.fd, "rb", closefd=False) as raw:
        for path, item in ((a, first), (b, second)):
            compare(
                path, item, raw, metadata["raw_bytes"], first["raw_sha256"], deadline, lease.check
            )
        if raw_digest(raw, deadline, lease.check) != first["raw_sha256"]:
            raise ValueError("offline source hash changed")
    lease.check()


def offline_pair(source, archive_a, archive_b, restored, *, project_root, acknowledge_unlink):
    if not acknowledge_unlink:
        raise ValueError("explicit offline source-unlink acknowledgment required")
    root, source, a, b, target, meta = paths(source, archive_a, archive_b, restored, project_root)
    deadline = Deadline(SECONDS)
    metadata, original, first, second, credit = create_pair(source, a, b, root, deadline)
    lease = Lease(source, original, deadline)
    try:
        with lease:
            _prove_pair(lease, a, b, metadata, first, second, deadline)
            require_space(root, target, deadline, metadata["raw_bytes"], credit)
            lease.check()
            write_metadata(meta, metadata, first, second)
            require_space(root, target, deadline, metadata["raw_bytes"], credit)
            lease.unlink()
        require_space(root, target, deadline, metadata["raw_bytes"])
        return restore_pair(a, b, meta, target, project_root=root, deadline=deadline)
    except BaseException as error:
        if lease.removed:
            raise RuntimeError(
                "source unlinked; retain the archive pair and metadata for manual recovery"
            ) from error
        raise


def manual_restore(archive_a, archive_b, metadata, restored, *, project_root):
    return restore_pair(
        archive_a,
        archive_b,
        metadata,
        restored,
        project_root=project_root,
        deadline=Deadline(SECONDS),
    )
