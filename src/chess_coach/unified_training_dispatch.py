"""Select an exact non-corpus unified learning policy."""

from .unified_training_canonical_promotion import is_forced_source
from .unified_training_canonical_promotion import is_source as canonical_source
from .unified_training_owned_capture import is_source as capture_source
from .unified_training_owned_fork import is_source as fork_source
from .unified_training_public_mate import is_source as public_source


def policy(row):
    if is_forced_source(row):
        from . import unified_canonical_forced_learning

        return unified_canonical_forced_learning
    if canonical_source(row):
        from . import unified_canonical_promotion_learning

        return unified_canonical_promotion_learning
    if capture_source(row):
        from . import unified_capture_learning

        return unified_capture_learning
    if fork_source(row):
        from . import unified_fork_learning

        return unified_fork_learning
    if public_source(row):
        from . import unified_public_mate_learning

        return unified_public_mate_learning
    return None
