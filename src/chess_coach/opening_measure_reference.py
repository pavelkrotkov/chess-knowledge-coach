"""Retain one complete all-legal-root opening iteration."""

from .decision_line_view import view_line
from .deep_execution_work import _valid
from .opening_decision_line_safety import lines_safe
from .opening_queue_line import compact
from .purpose_iteration_line import checked
from .purpose_iteration_work import update
from .style_score import score_ok


class ReferenceIterations:
    """Keep a complete single-depth ranking and whole-search work maxima."""

    def __init__(self, board, position, roots, bounds):
        self.board = board
        self.position = position
        self.roots = {move.uci() for move in roots}
        self.bounds = bounds
        self.pending = None
        self.best = []
        self.depth = None
        self.work = {"nodes": None, "depth": None, "time": None}
        self.invalid_work = False

    def add(self, info):
        # Every search update contributes to the actual work bound, including
        # updates outside the final retained complete iteration.
        # Native string-only messages are annotations, not search updates.
        # Any update carrying search data must supply both work counters.
        if set(info) == {"string"}:
            return
        if not _valid(info.get("nodes"), True) or not _valid(info.get("time"), False):
            self.invalid_work = True
        update(self.work, info)
        rank = info.get("multipv")
        if type(rank) is not int or not 1 <= rank <= len(self.roots):
            return
        self._ranked(rank, info)

    def _ranked(self, rank, info):
        # A new rank one begins an iteration; partial rankings cannot be mixed.
        if rank == 1:
            self.pending = []
        if self.pending is None or rank != len(self.pending) + 1:
            self.pending = None
            return
        item = self._line(info)
        if item is None:
            self.pending = None
            return
        self.pending.append({"rank": rank, "line": item})
        if rank == len(self.roots):
            self._retain()

    def _line(self, info):
        # The report promises a checked prefix, not every later engine ply.
        pv = info.get("pv")
        if not isinstance(pv, list) or len(pv) < self.bounds[2]:
            return None
        item = checked(self.position, self.board, {**info, "pv": pv[:4]}, self.bounds)
        if item is None:
            return None
        line = view_line(item["line"], self.board, self.position["uci"])
        if not score_ok(line) or not lines_safe(self.board, [line]):
            return None
        return compact(line)

    def _retain(self):
        pending = self.pending
        if pending is None:
            return
        lines = [item["line"] for item in pending]
        if not self._complete(lines):
            return
        depth = lines[0]["depth"]
        if self.depth is None or depth >= self.depth:
            self.best = pending
            self.depth = depth

    def _complete(self, lines):
        roots = {line["root_move"] for line in lines}
        depths = {line["depth"] for line in lines}
        return (
            roots == self.roots
            and len(depths) == 1
            and lines[0]["score_value"] == max(line["score_value"] for line in lines)
        )
