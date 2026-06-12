"""Small shared helpers for assess scoring modules."""

def _as_string_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [
        str(item).strip()
        for item in values
        if str(item or "").strip()
    ]

def _type_def_valid(nc, type_name: str, value: str) -> bool:
    type_def = getattr(nc, "types", {}).get(type_name)
    return type_def.validate(value) if type_def else True
