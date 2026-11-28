"""Choose one fork window and its independent immutable source binding."""

from .opening_public_fork_later import bound as full_bound
from .opening_public_fork_later import branches as later_branches
from .opening_public_pin_policy import policy as pin_policy
from .opening_public_prevention_policy import prevention
from .opening_public_proof_prepare import branches
from .opening_public_proof_versions import combined, continuation


def _full_selection(base, root, subject, deadline, forks, window, *, prevent, pin):
    if forks or (pin and prevent) or window not in {"initial", "continuation"}:
        raise ValueError("invalid prevention selection" if prevent else "invalid pin selection")
    full, sha = full_bound(root, subject, deadline)
    selected_policy = pin_policy if pin else prevention
    return selected_policy(base, sha, window), (full, sha)


def select(base, root, subject, deadline, forks, window, *, prevent=False, pin=False):
    if pin or prevent:
        return _full_selection(
            base, root, subject, deadline, forks, window, prevent=prevent, pin=pin
        )
    if window == "continuation":
        if not forks:
            raise ValueError("fork preparation required")
        full, sha = full_bound(root, subject, deadline)
        return continuation(base, sha), (full, sha)
    if window != "initial":
        raise ValueError("invalid fork window")
    return (combined(base) if forks else base), None


def evaluate(index, base, identity, full, start, deadline):
    if "pin" in identity["policy"]:
        from .opening_public_pin import evaluate as pin_evaluate

        return pin_evaluate(full[0], identity, start, deadline)
    if "prevention" in identity["policy"]:
        from .opening_public_prevention import evaluate as prevention_evaluate

        return prevention_evaluate(full[0], identity, start, deadline)
    result, sample = branches(index, base if full else identity, start, deadline)
    if full is None:
        return result, sample, None
    later, coverage = later_branches(full[0], {**identity, "index_sha256": full[1]}, deadline)
    for label in ("played", "alternative"):
        result[label]["forks"] = later[label]
    return result, sample, coverage
