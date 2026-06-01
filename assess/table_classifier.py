"""Backward-compatible imports for the renamed table inspector module."""

from assess.table_inspector import (  # noqa: F401
    ClassifyResult,
    TableClassifier,
    TableInspectResult,
    TableInspector,
    build_prompt,
    dict_to_result,
    parse_response,
    result_to_dict,
    validate_columns,
)
