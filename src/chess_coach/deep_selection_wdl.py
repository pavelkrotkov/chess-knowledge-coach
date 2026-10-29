"""Compare native WDL distributions only when both are well formed."""


def _expected_score(wdl):
    if not isinstance(wdl, list) or len(wdl) != 3:
        return None
    if (
        any(type(value) is not int or not 0 <= value <= 1000000000 for value in wdl)
        or sum(wdl) == 0
    ):
        return None
    return (wdl[0] + wdl[1] / 2) / sum(wdl)


def wdl_gap(best, played, threshold):
    left, right = _expected_score(best), _expected_score(played)
    return left is not None and right is not None and left - right >= threshold
