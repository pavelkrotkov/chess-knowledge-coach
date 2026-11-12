"""Describe bounded recognition unavailability without exposing source details."""


def unavailable(error):
    if "deadline" in str(error):
        return "The check timed out while verifying its source. Try again."
    if "changed" in str(error):
        return "The check changed while it was being verified. Try again."
    return "The check or its first-encounter status is unavailable."
