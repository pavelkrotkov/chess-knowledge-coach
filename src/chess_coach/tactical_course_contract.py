"""Immutable tactical-course versions, policies, and selection contracts."""

from .tactical_course_choice import from_pairs
from .tactical_course_selection import CURRENT_PAIRS, PAIRS

LEGACY_VERSION = "local-tactical-course-v1"
LEGACY_POLICY = "provisional-recurring-tactics-v1"
PREVIOUS_VERSION = "local-tactical-course-v2"
PREVIOUS_POLICY = "provisional-recurring-tactics-v2"
PROTECTION_VERSION = "local-tactical-course-v3"
PROTECTION_POLICY = "provisional-recurring-tactics-v3"
VERSION = "local-tactical-course-v4"
POLICY = "provisional-recurring-tactics-v4"
SELECTED_VERSION = "local-tactical-course-v5"
SELECTED_POLICY = "provisional-recurring-tactics-v5"
THEMATIC_VERSION = "local-tactical-course-v6"
THEMATIC_POLICY = "provisional-recurring-tactics-v6"
THEMATIC_SELECTED_VERSION = "local-tactical-course-v7"
THEMATIC_SELECTED_POLICY = "provisional-recurring-tactics-v7"
NAMED_VERSION = "local-tactical-course-v8"
NAMED_POLICY = "provisional-recurring-tactics-v8"
DEFAULT_ROLES_VERSION = "local-tactical-course-v9"
DEFAULT_ROLES_POLICY = "provisional-recurring-tactics-v9"
SELECTED_ROLES_VERSION = "local-tactical-course-v10"
SELECTED_ROLES_POLICY = "provisional-recurring-tactics-v10"
SELECTED_FORK_VERSION = "local-tactical-course-v11"
SELECTED_FORK_POLICY = "provisional-recurring-tactics-v11"
SELECTED_FORK_ROLES_VERSION = "local-tactical-course-v12"
SELECTED_FORK_ROLES_POLICY = "provisional-recurring-tactics-v12"
DEFAULT_FORK_VERSION = "local-tactical-course-v13"
DEFAULT_FORK_POLICY = "provisional-recurring-tactics-v13"
SELECTED_PROTECTION_ROLES_VERSION = "local-tactical-course-v14"
SELECTED_PROTECTION_ROLES_POLICY = "provisional-recurring-tactics-v14"
DEFAULT_PROTECTION_ROLES_VERSION = "local-tactical-course-v15"
DEFAULT_PROTECTION_ROLES_POLICY = "provisional-recurring-tactics-v15"
MIXED_SELECTED_VERSION = "local-tactical-course-v16"
MIXED_SELECTED_POLICY = "provisional-recurring-tactics-v16"
# Only selected fork versions use the eight-second slice; the default keeps two seconds.
FORK_VERSIONS = {SELECTED_FORK_VERSION, SELECTED_FORK_ROLES_VERSION}
QUALIFIED_FORK_VERSIONS = {
    *FORK_VERSIONS,
    DEFAULT_FORK_VERSION,
    DEFAULT_PROTECTION_ROLES_VERSION,
    MIXED_SELECTED_VERSION,
}
ROLE_COURSE_VERSIONS = {
    DEFAULT_ROLES_VERSION,
    SELECTED_ROLES_VERSION,
    SELECTED_FORK_ROLES_VERSION,
    DEFAULT_FORK_VERSION,
    SELECTED_PROTECTION_ROLES_VERSION,
    DEFAULT_PROTECTION_ROLES_VERSION,
    MIXED_SELECTED_VERSION,
}
FORK_PAIR = ("fork", "execute")
CONTRACTS = {
    LEGACY_VERSION: (LEGACY_POLICY, PAIRS),
    PREVIOUS_VERSION: (PREVIOUS_POLICY, CURRENT_PAIRS),
    PROTECTION_VERSION: (PROTECTION_POLICY, CURRENT_PAIRS),
    VERSION: (POLICY, CURRENT_PAIRS),
    SELECTED_VERSION: (SELECTED_POLICY, None),
    THEMATIC_VERSION: (THEMATIC_POLICY, CURRENT_PAIRS),
    THEMATIC_SELECTED_VERSION: (THEMATIC_SELECTED_POLICY, None),
    NAMED_VERSION: (NAMED_POLICY, None),
    DEFAULT_ROLES_VERSION: (DEFAULT_ROLES_POLICY, CURRENT_PAIRS),
    SELECTED_ROLES_VERSION: (SELECTED_ROLES_POLICY, None),
    SELECTED_FORK_VERSION: (SELECTED_FORK_POLICY, [FORK_PAIR]),
    SELECTED_FORK_ROLES_VERSION: (SELECTED_FORK_ROLES_POLICY, [FORK_PAIR]),
    DEFAULT_FORK_VERSION: (DEFAULT_FORK_POLICY, CURRENT_PAIRS),
    DEFAULT_PROTECTION_ROLES_VERSION: (DEFAULT_PROTECTION_ROLES_POLICY, CURRENT_PAIRS),
    MIXED_SELECTED_VERSION: (MIXED_SELECTED_POLICY, None),
    SELECTED_PROTECTION_ROLES_VERSION: (
        SELECTED_PROTECTION_ROLES_POLICY,
        [("hanging_piece", "prevent")],
    ),
}


NAMED = {NAMED_VERSION, SELECTED_ROLES_VERSION}
SELECTED = {
    SELECTED_VERSION,
    THEMATIC_SELECTED_VERSION,
    SELECTED_PROTECTION_ROLES_VERSION,
    MIXED_SELECTED_VERSION,
    *FORK_VERSIONS,
    *NAMED,
}
THEMATIC = {
    THEMATIC_VERSION,
    DEFAULT_ROLES_VERSION,
    DEFAULT_FORK_VERSION,
    DEFAULT_PROTECTION_ROLES_VERSION,
} | (SELECTED - {SELECTED_VERSION})
MODERN = {PROTECTION_VERSION, VERSION, SELECTED_VERSION, *THEMATIC}


def pairs_for(kind, saved_pairs):
    contract = CONTRACTS[kind]
    if kind not in SELECTED:
        return contract[1]
    result = from_pairs(saved_pairs)
    if kind == MIXED_SELECTED_VERSION and len(result) < 2:
        raise ValueError("mixed selection requires multiple pairs")
    required = [("hanging_piece", "execute")] if kind in NAMED else contract[1]
    if required is not None and result != required:
        raise ValueError(
            "named capture selection differs" if kind in NAMED else "selected fork differs"
        )
    return result
