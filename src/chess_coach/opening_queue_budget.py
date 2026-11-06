"""Use cooperative short database guards in browser request threads."""

import sqlite3
import time
from contextlib import ExitStack, contextmanager

from .recurrence_snapshot import read_snapshot
from .tactical_course_budget import SLICE_SECONDS, Budget, PreviewUnavailable


class BrowserBudget(Budget):
    @contextmanager
    def scope(self, *, snapshot):
        self.check()
        until = min(self.expires, time.monotonic() + SLICE_SECONDS)
        self.db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
        try:
            with ExitStack() as stack:
                if snapshot:
                    stack.enter_context(read_snapshot(self.db))
                yield
                if time.monotonic() >= until:
                    raise PreviewUnavailable("request deadline reached")
        except sqlite3.OperationalError as error:
            if (
                getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT
                and time.monotonic() >= until
            ):
                raise PreviewUnavailable("request deadline reached") from None
            raise
        finally:
            self.db.connection.set_progress_handler(None, 0)
        self.check()

    @contextmanager
    def publication(self):
        with self.scope(snapshot=True):
            self.db.connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            self.check()
            yield
