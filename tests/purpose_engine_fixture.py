"""Synthetic engine driver for candidate diagnostics."""

from tests.purpose_engine_lines import assert_outside_transaction, candidate_roots
from tests.purpose_engine_score import candidate_line


class CandidateEngine:
    def __init__(self, db, mode="normal", change=None):
        self.id = {"name": "Synthetic"}
        self.options = {}
        self.db = db
        self.mode = mode
        self.change = change
        self.calls = []
        self.closed = False

    def configure(self, settings):
        assert_outside_transaction(self.db)
        self.settings = settings

    def analyse(self, board, limit, multipv, root_moves=None):
        assert_outside_transaction(self.db)
        self.calls.append((board.copy(), limit, multipv, root_moves))
        if self.mode == "timeout":
            raise TimeoutError("synthetic")
        roots = candidate_roots(board, root_moves, self.mode)
        final = root_moves is not None
        lines = [candidate_line(board, move, i, self.mode, final) for i, move in enumerate(roots)]
        if self.mode == "missing" and final:
            lines = lines[:1]
        if self.change is not None and final:
            self.change()
        return lines

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True
