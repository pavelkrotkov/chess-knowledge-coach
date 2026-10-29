"""Validate the independently bounded pipeline workers."""

from .material_worker_config import validate_material_config
from .pipeline_deep_config import deep_options, validate_deep_config
from .pipeline_endgame_config import validate_endgame_config


def validate_worker_config(config):
    validate_deep_config(config)
    deep_options(config)
    validate_material_config(config)
    validate_endgame_config(config)
