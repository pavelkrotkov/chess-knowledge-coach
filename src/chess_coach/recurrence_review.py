"""Describe review state without treating it as a mastery claim."""


def review(row):
    if row["review_decision"] == "accept":
        if (
            row["human_validated"] == 1
            and isinstance(row["review_actor"], str)
            and row["review_actor"].strip()
        ):
            return "accepted"
        return "invalid acceptance"
    return "legacy acceptance" if row["human_validated"] == 1 else "unreviewed"
