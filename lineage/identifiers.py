"""Identifier normalization helpers shared by lineage tools."""

from __future__ import annotations


def canonical_identifier(name) -> str:
    """Return the logical identifier name without SQL quote wrappers."""
    if name is None:
        return ""
    text = str(name).strip()
    while len(text) >= 2 and (
        (text[0] == text[-1] == "`") or (text[0] == text[-1] == '"')
    ):
        text = text[1:-1].strip()
    return text


def identifier_match_key(name) -> str:
    """Return the case-insensitive key used for identifier matching."""
    return canonical_identifier(name).casefold()


def canonical_qualified_identifier(name) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    return ".".join(
        canonical_identifier(part)
        for part in text.split(".")
        if str(part).strip()
    )


def table_identity(name, default_catalog="internal", default_db="") -> tuple:
    """Return (catalog, database, table), filling defaults as needed."""
    full_name = canonical_qualified_identifier(name)
    parts = [part for part in full_name.split(".") if part]
    if not parts:
        return "", "", ""

    catalog = canonical_identifier(default_catalog) or "internal"
    database = canonical_identifier(default_db)
    if len(parts) == 1:
        return catalog, database, parts[0]
    if len(parts) == 2:
        return catalog, parts[0], parts[1]
    return parts[-3], parts[-2], parts[-1]


def schema_table_match_key(catalog, database, table) -> tuple:
    return (
        identifier_match_key(catalog),
        identifier_match_key(database),
        identifier_match_key(table),
    )


def table_identity_match_key(
    name,
    default_catalog="internal",
    default_db="",
) -> tuple:
    catalog, database, table = table_identity(
        name,
        default_catalog=default_catalog,
        default_db=default_db,
    )
    return schema_table_match_key(catalog, database, table)


def qualified_table_name(catalog, database, table) -> str:
    catalog = canonical_identifier(catalog)
    database = canonical_identifier(database)
    table = canonical_identifier(table)
    return ".".join(part for part in (catalog, database, table) if part)


def display_table_name(
    name,
    *,
    default_catalog="internal",
    default_db="",
    strip_current_db=False,
) -> str:
    """Format a table name for output, hiding the default internal catalog."""
    catalog, database, table = table_identity(
        name,
        default_catalog=default_catalog,
        default_db=default_db,
    )
    if not table:
        return ""
    if identifier_match_key(catalog) != identifier_match_key(default_catalog):
        return qualified_table_name(catalog, database, table)
    if strip_current_db and identifier_match_key(
        database
    ) == identifier_match_key(default_db):
        return table
    if database:
        return f"{database}.{table}"
    return table


def short_table_name(table_name) -> str:
    """Return the final table segment after stripping SQL quote wrappers."""
    name = canonical_qualified_identifier(str(table_name or "").rstrip(";"))
    if not name:
        return ""
    return name.split(".")[-1].strip()


def split_column_ref(ref) -> tuple | None:
    """Split a table.column reference, preserving display identifiers."""
    text = canonical_qualified_identifier(ref)
    if "." not in text:
        return None
    table_name, column_name = text.rsplit(".", 1)
    if not table_name or not column_name:
        return None
    return table_name, column_name


def column_ref_match_key(ref) -> tuple:
    split_ref = split_column_ref(ref)
    if split_ref is None:
        return "", ""
    table_name, column_name = split_ref
    return identifier_match_key(table_name), identifier_match_key(column_name)
