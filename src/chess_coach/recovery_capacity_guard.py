"""Check actual SQLite copy growth before it can be published."""

import shutil
import sqlite3
import time
from pathlib import Path

from .recovery_capacity import PROJECT_LIMIT, RESERVE, allocated


class Guard:
    def __init__(self, root, temporary, report, deadline):
        self.root = root
        self.temporary = temporary
        self.report = report
        self.deadline = deadline
        self.next_check = time.monotonic() + 30

    def progress(self, status, remaining, total):
        self.deadline.backup_progress(status, remaining, total)
        if (
            status not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
            and total != self.report["page_count"]
        ):
            raise ValueError("pinned database size changed")
        # Check this destination each chunk; rescan the project periodically.
        self.check_files()
        if time.monotonic() >= self.next_check:
            self.final()
            self.next_check = time.monotonic() + 30

    def check_files(self):
        total = 0
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = Path(str(self.temporary) + suffix)
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            # Include both apparent size and filesystem allocation of companions.
            total += max(info.st_size, info.st_blocks * 512)
        if total > self.report["snapshot_bytes"] + self.report["working_bytes"]:
            raise ValueError("recovery copy exceeded its reserved space")
        if shutil.disk_usage(self.temporary.parent).free < RESERVE:
            raise ValueError("recovery disk reserve unavailable")

    def final(self):
        self.deadline.check()
        self.check_files()
        if allocated(self.root, self.deadline) + RESERVE > PROJECT_LIMIT:
            raise ValueError("project storage reserve unavailable")
        self.deadline.check()
