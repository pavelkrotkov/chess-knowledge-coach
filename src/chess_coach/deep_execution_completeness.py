"""Check that bounded search observations are complete enough to present."""

from .deep_execution_compare import usable_line


def completeness(result, board, played, min_depth):
    if result["problem"]:
        return result["problem"]
    problem = _alternative_problem(result)
    if problem is not None:
        return problem
    alternatives = result["alternatives"]
    lines = [result["best"], result["played"], *(item["line"] for item in alternatives)]
    if any(not usable_line(line, board, played, min_depth) for line in lines):
        return "incomplete_line"
    if not result["best_work"]["nodes"] or not result["played_work"]["nodes"]:
        return "work_unavailable"
    return None


def _alternative_problem(result):
    alternatives, required = result["alternatives"], result["required_alternatives"]
    if required < 1 or len(alternatives) != required:
        return "missing_alternatives"
    if [item["rank"] for item in alternatives] != list(range(1, required + 1)):
        return "missing_alternatives"
    roots = [item["line"]["root_move"] for item in alternatives]
    if None in roots or len(set(roots)) != required:
        return "invalid_alternatives"
    return None
