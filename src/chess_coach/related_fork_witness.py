"""Select a legal fork proof branch with an original-target capture."""

from .related_fork_features import fork_features


def witness(prompt, proof):
    for branch in proof["branches"]:
        line = [proof["move"], branch["reply"], branch["capture"]]
        if fork_features(prompt, line):
            return " ".join(line)
    raise ValueError("unsupported fork witness")
