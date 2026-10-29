"""Publish a completed snapshot without replacing an existing version."""

import json
import os
import uuid

from .puzzle_snapshot_state import SOURCE_URL, write_state


def publish(path, attempt, state, manifest):
    temporary = attempt / ("manifest-" + uuid.uuid4().hex + ".json")
    with temporary.open("x", encoding="utf-8") as out:
        json.dump(manifest, out, indent=2, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.chmod(temporary, 0o444)
    os.link(temporary, path / "manifest.json")
    state.update(
        phase="ready",
        csv_path=manifest["csv_path"],
        csv_sha256=manifest["csv_sha256"],
        archive_sha256=manifest["archive_sha256"],
    )
    write_state(attempt, state)


def make_manifest(version, archive, csv, archive_hash, csv_hash):
    return {
        "manifest_version": 1,
        "version": version,
        "source_url": SOURCE_URL,
        "csv_path": str(csv.resolve()),
        "csv_sha256": csv_hash,
        "archive_sha256": archive_hash,
        "archive_bytes": archive.stat().st_size,
        "csv_bytes": csv.stat().st_size,
        "hash_origin": "locally computed",
    }
