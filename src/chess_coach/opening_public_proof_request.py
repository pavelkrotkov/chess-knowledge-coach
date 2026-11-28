"""Normalize and validate the complete public-preparation request grammar."""


def normalize(
    forks,
    prevent,
    protection,
    capture_pv,
    defense_pv,
    mate,
    window,
    *,
    short_mate=False,
    back_rank=False,
    skewer=False,
):
    if mate and any((protection, capture_pv, defense_pv)):
        raise ValueError("invalid mate selection")
    choices = (
        (skewer, "skewer"),
        (back_rank, "back_rank"),
        (short_mate, "short_mate"),
        (defense_pv, "defense_pv"),
        (capture_pv, "capture_pv"),
        (protection, "protection"),
        (prevent, "prevention"),
        (mate, "mate"),
        (forks, "fork"),
    )
    kind = next((name for enabled, name in choices if enabled), "capture")
    invalid = {
        "capture": (window == "continuation",),
        "defense_pv": (forks, prevent, protection, capture_pv, window != "initial"),
        "capture_pv": (forks, prevent, protection, window != "initial"),
        "protection": (forks, prevent, window != "initial"),
        "prevention": (forks, mate, window not in {"initial", "continuation"}),
        "mate": (forks, window not in {"initial", "continuation"}),
        "skewer": (
            forks,
            prevent,
            protection,
            capture_pv,
            defense_pv,
            mate,
            short_mate,
            back_rank,
            window not in {"initial", "continuation"},
        ),
        "back_rank": (
            forks,
            prevent,
            protection,
            capture_pv,
            defense_pv,
            mate,
            short_mate,
            window not in {"initial", "continuation"},
        ),
        "short_mate": (
            forks,
            prevent,
            protection,
            capture_pv,
            defense_pv,
            mate,
            window not in {"initial", "continuation"},
        ),
    }
    messages = {
        "capture": "fork preparation required",
        "defense_pv": "invalid defense observation selection",
        "capture_pv": "invalid capture observation selection",
        "protection": "invalid protection selection",
        "prevention": "invalid prevention selection",
        "mate": "invalid mate selection",
        "short_mate": "invalid short-mate selection",
        "back_rank": "invalid back-rank selection",
        "skewer": "invalid skewer selection",
    }
    if any(invalid.get(kind, ())):
        raise ValueError(messages[kind])
    if window not in {"initial", "continuation"}:
        raise ValueError("invalid fork window")
    return kind
