"""Initialize the bounded pawn-structure scan report."""


def new_report(config):
    return {
        "status": "disabled",
        "examined": 0,
        "attempted": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "capped": False,
        "pending": False,
        "scan_limited": False,
        "outcomes": {},
        "limits": {
            "positions": config.material_max_scan,
            "decisions": config.material_max_decisions,
        },
    }
