"""Cooperatively bound SQLite snapshot, backup, and comparison work."""

import sqlite3
import time

SECONDS = 300


class Deadline:
    def __init__(self):
        now = time.monotonic()
        self.end = now + SECONDS
        self.busy_end = now + 30

    def check(self):
        if time.monotonic() >= self.end:
            raise TimeoutError("database snapshot time limit exceeded")

    def progress(self):
        return int(time.monotonic() >= self.end)

    def backup_progress(self, status, remaining, total):
        self.check()
        now = time.monotonic()
        if status in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            if now >= self.busy_end:
                raise TimeoutError("SQLite backup could not acquire a read lock")
        else:
            self.busy_end = now + 30
