"""Rotate category priority and calculate planned slot quotas."""

from .deep_selection_categories import CATEGORIES


def rotated(game_key):
    offset = int(game_key[:2], 16) % len(CATEGORIES)
    return CATEGORIES[offset:] + CATEGORIES[:offset]


def targets(slots, game_key):
    order = rotated(game_key)
    return {
        category: slots // len(order) + int(index < slots % len(order))
        for index, category in enumerate(order)
    }
