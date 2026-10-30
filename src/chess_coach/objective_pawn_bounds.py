"""Compare bounded mover-perspective WDL intervals to the announced goal."""


def root_goal(proof):
    if proof.get("status") != "complete":
        return None
    lower, upper = proof.get("lower"), proof.get("upper")
    if type(lower) is not int or lower != upper or lower not in {0, 1}:
        return None
    return lower


def alternative(proof, move):
    matches = [
        item for item in proof.get("alternatives", []) if item.get("move", {}).get("uci") == move
    ]
    if len(matches) != 1:
        return None
    item = matches[0]
    low, high = item.get("lower"), item.get("upper")
    if type(low) is not int or type(high) is not int or not -1 <= low <= high <= 1:
        return None
    return low, high


def verdict(low, high, goal):
    if low >= goal:
        return "correct", "result_preserved"
    if high < goal:
        return "incorrect", "result_worsened"
    return "unresolved", "result_interval_overlaps_goal"
