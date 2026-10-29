"""Bounded material-preview history reuse inside one read-only snapshot."""

from collections import OrderedDict

from .learner_context import decision_context_boards
from .material_context import NotLearnerDecision
from .preview_game import PreviewGame
from .preview_guard import require_read_snapshot

MAX_GAMES = 4


class PreviewHistory:
    def __init__(self, db, learner):
        self.db = db
        self.learner = learner
        self.wanted = set()
        self.games = OrderedDict()

    def targets(self, position_ids):
        self.wanted = {value for value in position_ids if value is not None}

    def _game(self, game_id):
        game = self.games.get(game_id)
        if game is None:
            game = PreviewGame(
                decision_context_boards(self.db, game_id, learner=self.learner), self.wanted
            )
            self.games[game_id] = game
            if len(self.games) > MAX_GAMES:
                self.games.popitem(last=False)
        self.games.move_to_end(game_id)
        return game

    def _entry(self, game_id, position_id):
        require_read_snapshot(self.db.connection)
        if position_id not in self.wanted:
            raise ValueError("position outside preview")
        return self._game(game_id).entry(position_id)

    def context(self, game_id, position_id):
        context, _board = self._entry(game_id, position_id)
        if context["subject"] is None:
            raise NotLearnerDecision("not a learner decision")
        return context.copy()

    def board(self, game_id, position_id):
        _context, board = self._entry(game_id, position_id)
        return board.copy()

    def clear(self):
        self.games.clear()
        self.wanted.clear()
