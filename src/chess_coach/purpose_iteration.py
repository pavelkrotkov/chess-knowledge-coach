"""Retain one structurally complete native MultiPV iteration."""

from .purpose_iteration_line import DEFAULT_BOUNDS, checked, paired
from .purpose_iteration_work import update


class Iterations:
    def __init__(self, board, position, roots, bounds=None):
        self.board = board
        self.position = position
        self.roots = {move.uci() for move in roots}
        self.pending = None
        self.best = []
        self.depth = None
        self.work = {"nodes": None, "depth": None, "time": None}
        self.bounds = bounds or DEFAULT_BOUNDS
        self.priority = (False, 0)

    def add(self, info):
        update(self.work, info)
        rank = info.get("multipv")
        if type(rank) is not int or rank not in (1, 2):
            return
        item = checked(self.position, self.board, info, self.bounds)
        if rank == 1:
            self.pending = item
            return
        first, self.pending = self.pending, None
        pair = paired(first, item, self.roots)
        if pair is None:
            return
        first, item = pair
        depth = item["line"]["depth"]
        length = min(len(first["line"]["pv"].split()), len(item["line"]["pv"].split()))
        priority = (length >= self.bounds[2], depth)
        if priority >= self.priority:
            self.priority = priority
            self.best = [{"rank": 1, "line": first["line"]}, {"rank": 2, "line": item["line"]}]
            self.depth = depth
