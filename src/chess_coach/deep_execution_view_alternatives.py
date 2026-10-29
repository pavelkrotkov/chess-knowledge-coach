"""Validate that stored ranked alternatives cover the requested legal moves."""


def alternatives_present(result, board):
    required = min(result["limits"]["multipv"], board.legal_moves.count())
    alternatives = result["alternatives"]
    if required < 1 or len(alternatives) != required:
        return False
    if [item["rank"] for item in alternatives] != list(range(1, required + 1)):
        return False
    roots = [item["line"]["root_move"] for item in alternatives]
    return len(set(roots)) == required
