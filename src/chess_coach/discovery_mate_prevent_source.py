"""Replay or publish the existing immediate discovered-mate source."""

from functools import partial

from .discovery_defense_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION
from .discovery_defense_observation import observe
from .discovery_prevent_mapping import mapping
from .fork_publish import publish
from .fork_replay import current_result
from .fork_storage import fact_run
from .material_source_marker import source_marker


def process_source(db, source, *, started=None):
    replay = current_result(
        db, source, producer=PRODUCER, mapper=MAPPER, version=VERSION, fact_type=FACT
    )
    if replay is not None:
        if (
            source_marker(
                db, source["position_id"], source["game_id"], source["context"]["subject"]
            )
            != source["source_marker"]
        ):
            raise ValueError("discovery defense source changed")
        return replay
    fact = observe(
        source["board"],
        source["context"]["played_move"],
        source["best"],
        source["played"],
        started=started,
    )
    writer = partial(fact_run, producer=PRODUCER, version=VERSION, fact_type=FACT)
    mapper = partial(mapping, mapper=MAPPER, version=VERSION, scope=SCOPE)
    return publish(db, source, fact, fact_writer=writer, mapping_writer=mapper)
