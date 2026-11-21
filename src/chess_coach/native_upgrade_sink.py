"""Bound the discarded output of a read-only recovery verification."""


class Sink:
    def write(self, chunk):
        return len(chunk)


class Guard:
    def __init__(self, deadline):
        self.deadline = deadline

    def check(self, _remaining):
        self.deadline.check()
