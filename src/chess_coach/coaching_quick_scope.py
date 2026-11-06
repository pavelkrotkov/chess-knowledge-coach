"""Allowlisted coaching patterns and bounded quick-preview defaults."""

from .recurrence_skills import PAIRS

DEFAULT = (
    ("hanging_piece", "execute"),
    ("hanging_piece", "prevent"),
    ("mate_in_one", "execute"),
    ("calculation", "execute"),
)


def label(pair):
    names = {
        ("hanging_piece", "execute"): "Finding captures",
        ("hanging_piece", "prevent"): "Protecting pieces",
        ("mate_in_one", "execute"): "Mate in one",
        ("calculation", "execute"): "Short-mate calculation",
    }
    skill, operation = pair
    return names.get(pair, f"{skill.replace('_', ' ').capitalize()} · {operation}")


def patterns():
    return [
        {"key": f"{skill}.{operation}", "label": label((skill, operation))}
        for skill, operation in PAIRS
    ]


def selected(value):
    if value is None:
        return DEFAULT
    match = next(
        ((skill, operation) for skill, operation in PAIRS if value == f"{skill}.{operation}"), None
    )
    if match is None:
        raise ValueError("unsupported coaching pattern")
    return (match,)
