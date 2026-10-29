"""Retain bounded validated source summaries for one preview."""

from collections import OrderedDict

from .deep_selection_source import source_snapshot

MAX_GAMES = 4


class PreviewSources:
    def __init__(self, db, learner):
        self.db = db
        self.learner = learner
        self.values = OrderedDict()

    def get(self, game_id):
        summary = self.values.get(game_id)
        if summary is None:
            source = source_snapshot(self.db, game_id, self.learner)
            summary = {key: source[key] for key in ("cheap_run_id", "input_fingerprint")}
            self.values[game_id] = summary
            if len(self.values) > MAX_GAMES:
                self.values.popitem(last=False)
        self.values.move_to_end(game_id)
        return summary.copy()

    def clear(self):
        self.values.clear()
