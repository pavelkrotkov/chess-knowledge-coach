"""Write, validate and publish a composite compressed recovery."""

import json
import sqlite3
from contextlib import closing

from .recovery_fidelity import verify_fidelity
from .recovery_gzip_files import discard, publish, sync
from .recovery_gzip_files import temporary as temporary_file
from .recovery_gzip_guard import Guard
from .recovery_gzip_memory import configure
from .recovery_gzip_restore import restore
from .recovery_gzip_stream import compress
from .recovery_verify import verify_database


def _verify(reader, path, deadline):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as restored:
        restored.set_progress_handler(deadline.progress, 1000)
        restored.execute("PRAGMA query_only=ON")
        configure(restored)
        verify_database(restored)
        verify_fidelity(reader, restored, deadline)


def create(
    reader, raw, metadata, root, targets, report, deadline, *, compressor=None, restorer=None
):
    compressor = compressor or compress
    restorer = restorer or restore
    temporary = []
    published = []
    try:
        for target in targets:
            temporary.append(temporary_file(target))
        archive, restored, manifest_path = temporary
        guard = Guard(root, archive, report, deadline)
        guard.check(metadata["raw_bytes"], force=True)
        manifest = compressor(raw, archive, metadata, report, guard, deadline)
        sync(archive)
        restorer(archive, restored, manifest, guard, deadline)
        sync(restored)
        _verify(reader, restored, deadline)
        guard.check(0, force=True)
        manifest["restore_integrity"] = "ok"
        manifest["restore_foreign_keys"] = "ok"
        manifest["typed_fidelity"] = "ok"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        sync(manifest_path)
        publish(temporary, targets, published)
        return {"status": "verified"}
    except BaseException:
        discard(published)
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
