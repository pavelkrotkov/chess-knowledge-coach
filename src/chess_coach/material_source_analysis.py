"""Choose only current completed deep lines or the current cheap checkpoint."""


def current_lines(analysis, cheap_id):
    deep = analysis.get("deep")
    if deep and deep["status"] == "complete" and deep.get("result"):
        result = deep["result"]
        return (
            result["best"],
            result["played"],
            {
                "kind": "deep",
                "run_id": result["run_id"],
                "selection_id": deep["selection_id"],
                "job_id": deep["job_id"],
                "attempt_number": deep["attempt_number"],
                "cheap_run_id": cheap_id,
            },
        )
    return analysis["best"], analysis["played"], {"kind": "cheap", "run_id": cheap_id}
