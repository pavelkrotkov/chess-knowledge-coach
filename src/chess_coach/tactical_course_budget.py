"""Keep short snapshots consistent across one private tactical preview."""

import time
from contextlib import ExitStack, contextmanager

from .recurrence_snapshot import read_snapshot
from .tactical_course_deadline import deadline

TOTAL_SECONDS = 60.0
SLICE_SECONDS = 2.0


class PreviewUnavailable(Exception):
    """A tactical preview could not be built safely."""


class Budget:
    def __init__(self, db, *, slice_seconds=None):
        if db.connection.in_transaction:
            raise PreviewUnavailable("preview requires an idle connection")
        self.db = db
        # Selected background work can redistribute, but never extend, the
        # existing total deadline. Default and browser callers keep their policy.
        self.slice_seconds = slice_seconds
        self.expires = time.monotonic() + TOTAL_SECONDS
        self.version = self._version()
        self._familiar = None

    def _version(self):
        return self.db.connection.execute("PRAGMA data_version").fetchone()[0]

    def check(self):
        if time.monotonic() >= self.expires or self._version() != self.version:
            raise PreviewUnavailable("preview changed or deadline reached")

    @contextmanager
    def scope(self, *, snapshot):
        self.check()
        remaining = min(self.slice_seconds or SLICE_SECONDS, self.expires - time.monotonic())
        with deadline(self.db.connection, remaining), ExitStack() as stack:
            if snapshot:
                stack.enter_context(read_snapshot(self.db))
            yield
        self.check()

    @contextmanager
    def publication(self):
        self.check()
        remaining = min(self.slice_seconds or SLICE_SECONDS, self.expires - time.monotonic())
        with deadline(self.db.connection, remaining), read_snapshot(self.db):
            self.db.connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            self.check()
            yield
