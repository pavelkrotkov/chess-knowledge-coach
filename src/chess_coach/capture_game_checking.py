"""Qualify a checking capture only after every supported evasion."""

from .material_check_proof import checking_capture
from .material_check_rules import eligible as checking_eligible
from .material_exchange_rules import has_legal_recapture


def inspect(board, move):
    if not checking_eligible(board, move):
        return "unknown"
    if has_legal_recapture(board, move):
        return "outside"
    return "proved" if checking_capture(board, move) else "unknown"
