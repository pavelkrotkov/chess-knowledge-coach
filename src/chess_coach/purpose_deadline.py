"""Fit engine operation timeouts within the remaining worker budget."""

import time

ENGINE_TIMEOUT = 5.0
CLEANUP_RESERVE = 0.1


def startup_timeout(deadline):
    remaining = deadline - time.monotonic() - CLEANUP_RESERVE
    return min(ENGINE_TIMEOUT, remaining / 3) if remaining > 0 else None


def search_timeout(deadline, search_seconds):
    remaining = deadline - time.monotonic() - search_seconds - CLEANUP_RESERVE
    return min(ENGINE_TIMEOUT, remaining) if remaining > 0 else None


def cleanup_timeout(deadline):
    return max(0.001, min(ENGINE_TIMEOUT, deadline - time.monotonic()))
