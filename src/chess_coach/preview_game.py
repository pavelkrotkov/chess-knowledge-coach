"""Retain requested boards and decision contexts for one verified game history."""


class PreviewGame:
    def __init__(self, decisions, wanted):
        self.decisions = decisions
        self.wanted = wanted
        self.entries = {}
        self.contexts = None
        self.started = False
        self.error = None
        self.done = False

    def _advance(self):
        # A completed traversal validates every stored ply; retain full boards
        # only for the positions explicitly requested by this preview.
        self.started = True
        try:
            context, board = next(self.decisions)
        except StopIteration:
            self.done = True
            return
        except ValueError as error:
            self.error = error
            return
        if self.contexts is not None:
            self.contexts.append(context)
        if context["position_id"] in self.wanted:
            self.entries[context["position_id"]] = (context, board)

    def all_contexts(self):
        # Capture starts before the first move. If a board was requested first,
        # callers use the ordinary recurrence replay instead of a partial game.
        if self.contexts is None:
            if self.started:
                raise ValueError("history already partially consumed")
            self.contexts = []
        while not self.done and self.error is None:
            self._advance()
        if self.error is not None:
            raise self.error
        # Mastery adds canonical fields; copies protect later board lookups.
        return [context.copy() for context in self.contexts]

    def entry(self, position_id):
        while position_id not in self.entries and not self.done and self.error is None:
            self._advance()
        if position_id in self.entries:
            return self.entries[position_id]
        if self.error is not None:
            raise self.error
        raise ValueError("decision is not in game history")
