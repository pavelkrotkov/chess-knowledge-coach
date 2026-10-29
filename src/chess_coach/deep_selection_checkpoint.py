"""Validate that the cheap-analysis checkpoint still matches game inputs."""

from .analysis_comparison import SEMANTICS
from .pipeline_config import PipelineConfig
from .pipeline_inputs import analysis_input, game_input


def validate_checkpoint(db, game_id, stage, config):
    try:
        if (
            config["comparison_semantics"] != SEMANTICS
            or config["multipv"] != 1
            or config["played_multipv"] != 1
            or config["depth"] is not None
            or config["limits_apply_per_search"] is not True
        ):
            raise ValueError("unsupported cheap analysis")
        values = PipelineConfig(
            learner="selection",
            nodes=config["nodes"],
            seconds_per_position=config["time_limit"],
            threads=config["threads"],
            hash_mb=config["hash_mb"],
        )
        values.validate()
        expected = analysis_input(game_input(db, game_id), values, config["engine_sha256"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("current cheap analysis configuration is unavailable") from None
    if expected != stage["input_hash"]:
        raise ValueError("current cheap analysis no longer matches the game")
