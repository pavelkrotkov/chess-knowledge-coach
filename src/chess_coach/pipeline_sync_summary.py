"""Present bounded synchronization results without private details."""


def sync_summary(result: dict) -> dict:
    return {
        "status": "complete"
        if result["recent_complete"]
        and result["history_complete"]
        and not result["blocked_saturated"]
        else "partial",
        "games": result["games"],
        "requests": result["http_requests"],
        "bytes": result["http_bytes"],
        "windows": result["requests"],
        "recent_complete": result["recent_complete"],
        "history_complete": result["history_complete"],
        "blocked_saturated": result["blocked_saturated"],
    }
