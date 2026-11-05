"""Collect complete course familiarity in short, bounded primary-key pages."""

from .learner_identity import normalize_identity
from .puzzle_session_validate import validate_line
from .related_capture_familiar import LIMIT
from .related_capture_position import prompt_key
from .related_capture_probe import position_probe
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_familiar_games import _games, _pages


def _legacy(db, budget):
    prompts, count = set(), 0
    for rows in _pages(db, budget, "puzzle_sessions", "initial_fen,solution"):
        with budget.scope(snapshot=False):
            count += len(rows)
            if count > LIMIT:
                raise ValueError("familiarity scan limit exceeded")
            prompts.update(
                prompt_key(validate_line(row["initial_fen"], row["solution"])) for row in rows
            )
    return prompts


def _collect(db, subject, budget):
    identity = normalize_identity(subject)
    if not identity:
        raise ValueError("practice subject unavailable")
    prompts, games = _games(db, identity, budget)
    prompts.update(_legacy(db, budget))
    budget.check()
    return frozenset(prompts), frozenset(games), position_probe(db, identity, subject)


def familiarity(db, subject, budget):
    if budget._familiar is False:
        raise PreviewDeadline()
    if budget._familiar is None:
        try:
            budget._familiar = (subject, _collect(db, subject, budget))
        except PreviewDeadline:
            budget._familiar = False
            raise
    budget.check()
    if budget._familiar[0] != subject:
        raise ValueError("familiarity subject changed")
    return budget._familiar[1]
