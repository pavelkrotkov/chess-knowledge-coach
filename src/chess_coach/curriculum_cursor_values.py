"""Validate scalar cursor coordinates."""


def integer(value, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def text(value, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum
