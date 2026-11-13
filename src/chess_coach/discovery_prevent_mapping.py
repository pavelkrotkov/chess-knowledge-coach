"""Record an immutable source-linked discovery prevention mapping."""

from .mapping_runs import record_mapping_run_in_transaction


def mapping(db, source, inputs, run, fact, *, mapper, version, scope):
    if fact is None:
        return None
    context = source["context"]
    details = {
        "observation": fact,
        "provenance": source["provenance"],
        "qualification": "Provisional bounded observation. Mastery and intent remain unknown.",
    }
    item = {
        "skill": "discovered_attack",
        "outcome": fact["outcome"],
        "confidence": 0.5,
        "fact_ids": run["fact_ids"],
        "context": details,
        "observation_at": context["observation_at"],
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=source["position_id"],
        producer=mapper,
        mapper_version=version,
        subject=context["subject"],
        operation="prevent",
        scope_key=scope,
        input_data={"source": inputs, "fact_run": run["run_id"], "context": details},
        mappings=[item],
    )
