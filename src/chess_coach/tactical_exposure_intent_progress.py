"""Check coverage of legacy per-chapter publication states."""


def uncovered(state, chapters):
    progress = state.get("chapters")
    if not isinstance(progress, list) or len(progress) > 63:
        raise ValueError("tactical Study exposure unavailable")
    if not set(progress) <= {"new", "pending", "done"}:
        raise ValueError("tactical Study exposure unavailable")
    if not set(chapters) <= {str(i) for i in range(len(progress))}:
        raise ValueError("tactical Study exposure unavailable")
    return any(
        value in {"pending", "done"} and str(index) not in chapters
        for index, value in enumerate(progress)
    )
