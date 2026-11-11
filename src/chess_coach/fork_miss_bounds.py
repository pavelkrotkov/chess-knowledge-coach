"""Withhold comparisons when unresolved opportunities could reverse their order."""


def separated(samples):
    left, right = samples
    if not left["uncertain"] and not right["uncertain"]:
        return True
    left_total = left["opportunities"] + left["uncertain"]
    right_total = right["opportunities"] + right["uncertain"]
    return (
        left["miss"] * right_total > (right["miss"] + right["uncertain"]) * left_total
        or right["miss"] * left_total > (left["miss"] + left["uncertain"]) * right_total
    )
