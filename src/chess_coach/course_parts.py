"""Lay out already-qualified course chapters without changing their identity."""

from .course_preview import preview_hash

MAX_CHAPTERS = 63


def _pack(groups):
    packed, current = [], []
    for group in groups:
        if not group:
            raise ValueError("empty lesson group")
        if current and len(current) + len(group) > MAX_CHAPTERS:
            packed.append(current)
            current = []
        while len(group) > MAX_CHAPTERS:
            packed.append(group[:MAX_CHAPTERS])
            group = group[MAX_CHAPTERS:]
        current.extend(group)
    if current:
        packed.append(current)
    return packed


def partition(groups, parent):
    """Describe exact parts; callers must establish the parent source qualification."""
    indexed, index = [], 0
    for number, group in enumerate(groups):
        indexed.append([(index + offset, number, chapter) for offset, chapter in enumerate(group)])
        index += len(group)
    packed = _pack(indexed)
    if not packed:
        raise ValueError("empty course")
    result = [_part(items, parent, number, packed) for number, items in enumerate(packed)]
    manifest = {
        "schema": "tactical-course-parts-v1",
        "parent_sha256": parent,
        "chapter_count": index,
        "part_count": len(result),
        "parts": result,
    }
    return {**manifest, "sha256": preview_hash(manifest)}



def _part(items, parent, number, packed):
    chapters = [item[2] for item in items]
    part = {
        "parent_sha256": parent,
        "number": number + 1,
        "count": len(packed),
        "indices": [item[0] for item in items],
        "chapters": chapters,
        "pgn": "\n\n".join(chapter["pgn"] for chapter in chapters) + "\n",
        "continues_previous": number > 0 and packed[number - 1][-1][1] == items[0][1],
        "continues_next": number + 1 < len(packed) and items[-1][1] == packed[number + 1][0][1],
    }
    return {**part, "sha256": preview_hash(part)}
