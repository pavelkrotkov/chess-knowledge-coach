"""Select a legal fork proof branch with an original-target capture."""

from .related_fork_features import fork_features


def witness(prompt, proof, *, check=None):
    tick = check or (lambda: None)
    for branch in proof["branches"]:
        tick()
        line = [proof["move"], branch["reply"], branch["capture"]]
        features = fork_features(prompt, line)
        tick()
        if features:
            return " ".join(line)
    raise ValueError("unsupported fork witness")
