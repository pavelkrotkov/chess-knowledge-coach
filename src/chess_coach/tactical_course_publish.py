"""Atomically publish one complete local preview without replacing another."""

import json
import os
import tempfile


def stage(output, value):
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output.parent, prefix=".tactical-preview-", delete=False
        ) as handle:
            name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return output.with_name(os.path.basename(name))
    except BaseException:
        if name is not None:
            os.unlink(name)
        raise


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(output, value, budget, *, readonly=False):
    temporary = None
    try:
        with budget.scope(snapshot=False):
            temporary = stage(output, value)
            if readonly:
                temporary.chmod(0o400)
        with budget.publication():
            os.link(temporary, output, follow_symlinks=False)
        _sync_directory(output.parent)
    except BaseException:
        if temporary is not None and output.exists() and os.path.samefile(temporary, output):
            output.unlink()
        raise
    finally:
        if temporary is not None:
            temporary.unlink()
