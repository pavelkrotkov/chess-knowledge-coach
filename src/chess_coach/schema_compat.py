"""Prepare and attach explicitly selected legacy service compatibility."""

from .opening_queue_files import read
from .opening_queue_write import write
from .schema_compat_identity import SLOT, VERSION, _context, configured, same_database, verify
from .schema_compat_views import install


def attest(path, connection):
    from .schema_compat_scan import inspect

    same_database(connection, path)
    directory, identity = _context(path)
    before = connection.execute("PRAGMA schema_version").fetchone()[0]
    cookie = inspect(connection)
    same_database(connection, path)
    if cookie != before or _context(path)[1] != identity:
        raise ValueError("database identity changed during preflight")
    slot = directory / SLOT
    previous = read(slot)
    if (slot.exists() or slot.is_symlink()) and (
        not isinstance(previous, dict) or previous.get("version") != VERSION
    ):
        raise ValueError("existing compatibility attestation is unavailable")
    write(slot, {"version": VERSION, **identity, "schema": cookie})


def attach(connection, path):
    verify(connection, path)
    install(connection)


def readonly(connection, path):
    try:
        if configured(path):
            attach(connection, path)
    except Exception:
        connection.close()
        raise
