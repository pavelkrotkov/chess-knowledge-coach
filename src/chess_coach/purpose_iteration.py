"""Retain one structurally complete native MultiPV iteration."""

from .purpose_iteration_line import checked, paired
from .purpose_iteration_work import update


class Iterations:
    def __init__(self, board, position, roots):
        self.board = board
        self.position = position
        self.roots = {move.uci() for move in roots}
        self.pending = None
        self.best = []
        self.depth = None
        self.work = {"nodes": None, "depth": None, "time": None}

    def add(self, info):
        update(self.work, info)
        rank = info.get("multipv")
        if type(rank) is not int or rank not in (1, 2):
            return
        item = checked(self.position, self.board, info)
        if rank == 1:
            self.pending = item
            return
        first, self.pending = self.pending, None
        pair = paired(first, item, self.roots)
        if pair is None:
            return
        first, item = pair
        depth = item["line"]["depth"]
        if self.depth is None or depth >= self.depth:
            self.best = [{"rank": 1, "line": first["line"]}, {"rank": 2, "line": item["line"]}]
            self.depth = depth
