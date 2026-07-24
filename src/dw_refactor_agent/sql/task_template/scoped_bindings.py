"""Normalize external binding keys for one task-template parameter scope."""

from __future__ import annotations

from typing import Mapping, Optional

from .errors import TemplateRenderError


def _source_alias(source: Optional[str], prefix: str) -> Optional[str]:
    marker = f"{prefix}."
    if source and source.startswith(marker):
        return source[len(marker) :]
    return None


def scope_bindings(
    definitions,
    values: Mapping[str, object],
    *,
    source_prefix: str,
) -> dict:
    """Resolve prop, full source, and external source-alias keys uniformly."""
    scoped = {}
    claimed_aliases = {}
    for definition in definitions:
        keys = [definition.prop]
        if definition.source:
            keys.append(definition.source)
        alias = _source_alias(definition.source, source_prefix)
        if alias:
            keys.append(alias)
        candidates = [(key, values[key]) for key in keys if key in values]
        if not candidates:
            continue
        first_value = candidates[0][1]
        if any(value != first_value for _key, value in candidates[1:]):
            raise TemplateRenderError(
                f"conflicting {source_prefix} values for {definition.prop!r}",
                code="template.render.conflicting_binding",
                path=(definition.prop,),
            )
        for key, _value in candidates:
            previous = claimed_aliases.get(key)
            if previous is not None and previous != definition.prop:
                raise TemplateRenderError(
                    f"{source_prefix} binding {key!r} is ambiguous for "
                    f"{previous!r} and {definition.prop!r}",
                    code="template.render.ambiguous_binding",
                    path=(source_prefix, key),
                )
            claimed_aliases[key] = definition.prop
        scoped[definition.prop] = first_value
    return scoped


__all__ = ["scope_bindings"]
