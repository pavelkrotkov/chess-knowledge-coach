"""Lazily retain only requested decisions from one verified game history."""


class PreviewGame:
    def __init__(self, decisions, wanted):
        self.decisions = decisions
        self.wanted = wanted
        self.entries = {}
        self.error = None

    def entry(self, position_id):
        while position_id not in self.entries and self.error is None:
            try:
                context, board = next(self.decisions)
            except StopIteration:
                self.error = ValueError("decision is not in game history")
                break
            except ValueError as error:
                self.error = error
                break
            if context["position_id"] in self.wanted:
                self.entries[context["position_id"]] = (context, board)
        if position_id in self.entries:
            return self.entries[position_id]
        if self.error is not None:
            raise self.error
        raise ValueError("decision is not in game history")
