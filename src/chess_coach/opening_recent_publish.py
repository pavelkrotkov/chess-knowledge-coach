"""Publish the downloaded prefix and receipt without replacing an artifact."""

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .opening_queue_write import staged, sync
from .opening_recent_source import (
    KIND,
    LICENSE,
    LICENSE_URL,
    MANIFEST_NAME,
    MONTH,
    PREFIX_BYTES,
    PREFIX_NAME,
    SOURCE,
    URL,
)


def available(directory):
    target, manifest = directory / PREFIX_NAME, directory / MANIFEST_NAME
    if target.exists() or target.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise ValueError("public prefix already exists or requires inspection")
    return target, manifest


def publish(directory, content, identity):
    target, manifest = available(directory)
    receipt = {
        "kind": KIND,
        "source_url": URL,
        "month": MONTH,
        "range_start": 0,
        "range_end": PREFIX_BYTES - 1,
        "prefix_bytes": len(content),
        "prefix_sha256": hashlib.sha256(content).hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_page": SOURCE,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "whole_archive_checksum_verified": False,
        **identity,
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix=".opening-prefix-", delete=False
        ) as out:
            temporary = Path(out.name)
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        temporary.chmod(0o400)
        with staged(manifest, receipt) as staged_manifest:
            staged_manifest.chmod(0o400)
            os.link(temporary, target, follow_symlinks=False)
            os.link(staged_manifest, manifest, follow_symlinks=False)
            sync(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return receipt
