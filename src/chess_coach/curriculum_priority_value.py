"""Validate numeric bounds in a signed qualified evidence summary."""

import math


def bounds(value, limit):
    count = value["contexts"]
    if count is not None and (type(count) is not int or not 0 <= count <= limit):
        raise ValueError("invalid qualified evidence")
    _number(value["mastery"])
    _number(value["uncertainty"])
    if value["state"] == "sufficient" and (count is None or count < 3 or value["mastery"] is None):
        raise ValueError("invalid qualified evidence")


def _number(number):
    if number is None:
        return
    if type(number) not in {int, float} or not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("invalid qualified evidence")
