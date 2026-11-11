"""Traverse fixed evidence windows without losing continuation progress."""

from .protection_finder_sources import ROW_LIMIT, preferred
from .protection_finder_window import advance, load

SOURCE_LIMIT = 3


class Finder:
    def __init__(self, db, identity, state, checks):
        self.db, self.identity, self.state, self.checks = db, identity, state, checks
        self.scanned = 0
        self.partial = False
        self.finished = False
        self.page = []
        self.pending = []

    def run(self):
        while not self.finished and self.scanned < ROW_LIMIT and self.checks.checked < SOURCE_LIMIT:
            self.checks.check()
            if self.checks.result["items"]:
                break
            self.step()

    def step(self):
        if not self.page:
            self.page, self.pending = load(self.db, self.identity, self.state)
        if not self.page:
            if self.state[5]:
                advance(self.state)
            else:
                self.next_phase()
            return
        if not self.pending:
            advance(self.state)
            self.page = []
            return
        # Retain the whole window as context, including previously checked markers.
        row = self.pending.pop(0)
        self.scanned += 1
        # Advance before expensive verification so a deadline cannot trap continuation.
        self.state[4] = row["id"]
        preferred_source = preferred(self.page, row, self.state[1])
        if not self.pending:
            advance(self.state)
            self.page = []
        if preferred_source:
            self.checks.source(row["id"])

    def next_phase(self):
        if self.state[1] == 0:
            watermark = self.state[2]
            self.state[1:] = [1, watermark, watermark, watermark, 0]
            self.page = []
        else:
            self.finished = True
