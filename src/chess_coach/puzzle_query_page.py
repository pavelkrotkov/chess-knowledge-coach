"""Validate bounded puzzle query pagination."""


def validate_page(limit: int, offset: int) -> None:
    if limit < 1 or limit > 1000 or offset < 0:
        raise ValueError("limit must be 1..1000 and offset must be non-negative")


def validate_cursor(after_rating: int | None, after_id: str | None, offset: int) -> None:
    if (after_rating is None) != (after_id is None):
        raise ValueError("both keyset coordinates are required")
    if after_id is not None:
        _validate_id(after_id)
    if after_rating is not None and after_rating < 0:
        raise ValueError("invalid keyset rating")
    if after_id is not None and offset:
        raise ValueError("keyset pagination cannot be combined with offset")


def _validate_id(after_id: str) -> None:
    if not after_id or len(after_id) > 256:
        raise ValueError("invalid keyset puzzle ID")
