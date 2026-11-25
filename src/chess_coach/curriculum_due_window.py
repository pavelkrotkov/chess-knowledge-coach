"""Allow previously offered new prompts to return once as due review."""


def eligible_again(candidate, seen, window):
    return bool(
        candidate is not None
        and window is not None
        and candidate["prompt_key"] in seen
        and candidate["prompt_key"] in window["repeat_due"]
    )


def take_again(candidate, seen, window):
    if eligible_again(candidate, seen, window):
        key = candidate["prompt_key"]
        seen.remove(key)
        window["repeat_due"].remove(key)
        window["new_seen"].remove(key)
