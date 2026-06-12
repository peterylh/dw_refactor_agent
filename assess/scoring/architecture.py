"""Compatibility wrapper for model design scoring."""

from assess.scoring.model_design import score_model_design_health


def score_architecture_health(*args, **kwargs) -> dict:
    return score_model_design_health(*args, **kwargs)
