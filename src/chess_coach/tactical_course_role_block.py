"""Validate one ordered role block and its admitted practice source."""


def group(chapters, index, *, practice_sources=("corpus",)):
    pair = chapters[index : index + 2]
    if [(item.get("role"), item["source"]["type"]) for item in pair] != [
        ("explanation", "own-game"),
        ("worked", "own-game"),
    ]:
        raise ValueError("capture chapter order differs")
    end = index + 2
    if end < len(chapters) and chapters[end].get("role") == "practice":
        if chapters[end]["source"]["type"] not in practice_sources:
            raise ValueError("capture practice source differs")
        end += 1
    return chapters[index:end], end
