"""Screen harder candidates before spending the shared protection proof budget."""

from .related_capture_position import prompt_key
from .related_capture_rank import _excluded
from .related_protection_match import _prompt


def accepts(item, source, familiar_data, difficulty, counts):
    try:
        band, side = difficulty
        if item["type"] != "corpus" or item["rating"] // 200 != band:
            return False
        # A corpus line's first move produces the learner's prompt.
        if item["fen"].split()[1] == side[0]:
            return False
        prompt, _ = _prompt(item)
        familiar, _, is_familiar = familiar_data
        reason = _excluded(
            prompt_key(prompt), prompt_key(source["prompt_fen"]), familiar, is_familiar
        )
        if reason:
            counts[reason] += 1
            return False
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False
