"""Construct and finalize bounded mate and back-rank worker reports."""


def initial(config):
    report = {
        "status": "disabled",
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "outcomes": {},
        "capped": False,
        "back_rank": {
            "attempted": 0,
            "processed": 0,
            "replayed": 0,
            "unavailable": 0,
            "outcomes": {},
            "attempt_limit": config.mate_max_decisions,
            "nodes_per_attack": 6000,
            "nodes_per_defense": 6000,
        },
        "limits": {
            "positions": config.mate_max_scan,
            "decisions": config.mate_max_decisions,
            "nodes_per_decision": 6000,
        },
    }
    return report


def capped(report):
    return (
        report["processed"] >= report["limits"]["decisions"]
        or report["back_rank"]["attempted"] >= report["back_rank"]["attempt_limit"]
    )


def finish(report):
    if report["capped"] or report["unavailable"] or report["back_rank"]["unavailable"]:
        report["status"] = "partial"
    return report
