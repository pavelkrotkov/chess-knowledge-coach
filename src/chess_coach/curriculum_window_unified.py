"""Validate optional plan-window offers inside a unified start transaction."""


def check(db, token, subject, source_type, version, key, training, item_id):
    if token is None:
        return None
    if not training or item_id is not None:
        raise ValueError("practice window offer changed")
    from .curriculum_window_offer_check import check as check_offer

    return check_offer(db, token, subject, source_type, version, key, "unified")


def finish(value):
    if value is not None:
        from .curriculum_window_offer_check import valid_time

        valid_time(value)
