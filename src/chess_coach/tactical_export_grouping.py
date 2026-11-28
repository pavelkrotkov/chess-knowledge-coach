"""Group versioned course chapters with their explicit source roles."""

from .tactical_course import (
    DEFAULT_FORK_VERSION,
    DEFAULT_PROTECTION_ROLES_VERSION,
    DEFAULT_ROLES_VERSION,
    FORK_VERSIONS,
    MATE_ROLE_VERSIONS,
    MIXED_SELECTED_VERSION,
    NAMED_VERSION,
    SELECTED_FORK_ROLES_VERSION,
    SELECTED_PROTECTION_ROLES_VERSION,
    SELECTED_ROLES_VERSION,
)
from .tactical_course_role_block import group as group


def chapters(chapters, index, pattern, kind):
    if kind in MATE_ROLE_VERSIONS or (kind, pattern["kind"]) in {
        (DEFAULT_ROLES_VERSION, "capture"),
        (SELECTED_ROLES_VERSION, "capture"),
        (SELECTED_FORK_ROLES_VERSION, "fork"),
        (DEFAULT_FORK_VERSION, "capture"),
        (DEFAULT_FORK_VERSION, "fork"),
        (SELECTED_PROTECTION_ROLES_VERSION, "protection"),
        (DEFAULT_PROTECTION_ROLES_VERSION, "protection"),
        (DEFAULT_PROTECTION_ROLES_VERSION, "capture"),
        (DEFAULT_PROTECTION_ROLES_VERSION, "fork"),
        (MIXED_SELECTED_VERSION, "capture"),
        (MIXED_SELECTED_VERSION, "fork"),
        (MIXED_SELECTED_VERSION, "protection"),
    }:
        chapters, end = group(
            chapters,
            index,
            practice_sources=("corpus", "public")
            if pattern["kind"] in {"mate", "short_mate"}
            else ("corpus",),
        )
        return chapters, end, True, pattern["kind"] != "protection"
    if index >= len(chapters) or chapters[index]["source"]["type"] != "own-game":
        raise ValueError("owned chapter order differs")
    end = index + 1
    if end < len(chapters) and chapters[end]["source"]["type"] in {"public", "corpus"}:
        end += 1
    return chapters[index:end], end, False, kind in {NAMED_VERSION, *FORK_VERSIONS}
