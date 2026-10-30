"""Promotion proof horizons and resource bounds fail closed."""

import pytest


@pytest.mark.parametrize(
    "objective,moves",
    [
        ("promote_now", ["a6a7"]),
        ("promote_now", ["a7a8q", "h8g7", "a8a7"]),
        ("force_promotion_within_two", ["a6a7", "h8g7"]),
        ("force_promotion_within_two", ["a7a8q", "h8g7", "a8a7q"]),
    ],
)
def test_declared_promotion_horizon_rejects_incompatible_lines(objective, moves):
    from chess_coach.objective_promotion_line import validate

    with pytest.raises(ValueError, match="promotion line"):
        validate(moves, objective)
