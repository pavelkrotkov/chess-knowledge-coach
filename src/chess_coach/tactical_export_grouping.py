"""Group versioned course chapters with their explicit source roles."""

from .tactical_course import (
    DEFAULT_ROLES_VERSION,
    FORK_VERSIONS,
    NAMED_VERSION,
    SELECTED_FORK_ROLES_VERSION,
    SELECTED_ROLES_VERSION,
)


def group(chapters, index):
    pair = chapters[index : index + 2]
    if [(item.get("role"), item["source"]["type"]) for item in pair] != [
        ("explanation", "own-game"),
        ("worked", "own-game"),
    ]:
        raise ValueError("capture chapter order differs")
    end = index + 2
    if end < len(chapters) and chapters[end].get("role") == "practice":
        if chapters[end]["source"]["type"] != "corpus":
            raise ValueError("capture practice source differs")
        end += 1
    return chapters[index:end], end


def chapters(chapters, index, pattern, kind):
    if (kind, pattern["kind"]) in {
        (DEFAULT_ROLES_VERSION, "capture"),
        (SELECTED_ROLES_VERSION, "capture"),
        (SELECTED_FORK_ROLES_VERSION, "fork"),
    }:
        chapters, end = group(chapters, index)
        return chapters, end, True, True
    if index >= len(chapters) or chapters[index]["source"]["type"] != "own-game":
        raise ValueError("owned chapter order differs")
    end = index + 1
    if end < len(chapters) and chapters[end]["source"]["type"] in {"public", "corpus"}:
        end += 1
    return chapters[index:end], end, False, kind in {NAMED_VERSION, *FORK_VERSIONS}
