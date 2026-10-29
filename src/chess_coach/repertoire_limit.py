"""Validate the bounded attributable-game sample size."""

MAX_GAMES = 100


def validate_limit(limit):
    if type(limit) is not int or not 1 <= limit <= MAX_GAMES:
        raise ValueError("game limit must be an integer from 1 to 100")
    return limit
