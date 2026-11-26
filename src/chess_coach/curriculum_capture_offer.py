"""Sign and recheck one exact capture-practice recommendation."""

from .curriculum_prerequisite_token import encode

POLICY = "capture-practice-offer-v1"


def issue(db, state, item, goal, expires):
    return encode(
        db,
        [
            POLICY,
            state["subject_hash"],
            goal,
            expires,
            item["source_type"],
            item["source_version"],
            item["source_key"],
            {
                "revision": state["revision"],
                "capture_input": state["priority"]["capture_input"],
                "capture_sources": state["priority"]["capture_sources"],
            },
            "unified",
        ],
    )
