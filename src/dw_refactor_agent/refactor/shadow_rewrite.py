"""Role-aware, text-preserving SQL relation rewriting."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel
from sqlglot.tokens import Tokenizer, TokenType


class ShadowRewriteError(RuntimeError):
    """Raised when a selected relation has no safe shadow route."""


class ReferenceRole(Enum):
    WRITE = "write"
    DATA_READ = "data_read"
    SCHEMA_READ = "schema_read"
    LOCAL = "local"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RelationRoute:
    database: str
    table: str


@dataclass
class RewriteContext:
    prod_db: str
    qa_db: str
    write_routes: dict[str, RelationRoute] = field(default_factory=dict)
    schema_routes: dict[str, RelationRoute] = field(default_factory=dict)
    data_routes: dict[str, RelationRoute] = field(default_factory=dict)
    selected_tables: set[str] = field(default_factory=set)
    qa_ready_tables: set[str] = field(default_factory=set)
    required_qa_tables: set[str] = field(default_factory=set)
    current_job: str = ""
    strict: bool = False


@dataclass(frozen=True)
class RelationOccurrence:
    database: str
    table: str
    role: ReferenceRole
    start: int
    end: int
    raw: str
    physical: bool = True


def _canonical(value: str) -> str:
    return str(value or "").casefold()


def _is_backtick(token) -> bool:
    return token.token_type == TokenType.UNKNOWN and token.text == "`"


def _is_identifier(token) -> bool:
    return token.token_type in {TokenType.IDENTIFIER, TokenType.VAR}


def _statement_ranges(sql_text: str) -> list[tuple[int, int]]:
    ranges = []
    start = 0
    for token in Tokenizer(dialect="doris").tokenize(sql_text):
        if token.token_type == TokenType.SEMICOLON:
            candidate = sql_text[start : token.end + 1]
            if candidate.strip().strip(";").strip():
                ranges.append((start, token.end + 1))
            start = token.end + 1
    if sql_text[start:].strip():
        ranges.append((start, len(sql_text)))
    return ranges


def _component(tokens: list, index: int):
    if index >= len(tokens):
        return None
    start = tokens[index].start
    if _is_backtick(tokens[index]):
        if index + 2 >= len(tokens) or not _is_identifier(tokens[index + 1]):
            return None
        if not _is_backtick(tokens[index + 2]):
            return None
        return (
            tokens[index + 1].text,
            start,
            tokens[index + 2].end + 1,
            index + 3,
        )
    if not _is_identifier(tokens[index]):
        return None
    return tokens[index].text, start, tokens[index].end + 1, index + 1


def _relation(tokens: list, index: int):
    while index < len(tokens) and tokens[index].text.upper() in {
        "IF",
        "NOT",
        "EXISTS",
        "ONLY",
    }:
        index += 1
    first = _component(tokens, index)
    if first is None:
        return None
    value, start, end, index = first
    parts = [value]
    while index < len(tokens) and tokens[index].token_type == TokenType.DOT:
        next_component = _component(tokens, index + 1)
        if next_component is None:
            break
        value, _, end, index = next_component
        parts.append(value)
    return parts, start, end, index


def _first_keyword(tokens: list) -> str:
    return tokens[0].text.upper() if tokens else ""


def _cte_names(sql_text: str) -> set[str]:
    statements = sqlglot.parse(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    return {
        _canonical(cte.alias_or_name)
        for statement in statements
        if statement is not None
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }


def _context_role(
    tokens: list,
    index: int,
    first_keyword: str,
    write_target_seen: bool,
    schema_like: bool,
):
    token = tokens[index]
    text = token.text.upper()
    if token.token_type == TokenType.LIKE or text == "LIKE":
        return ReferenceRole.SCHEMA_READ if schema_like else None
    if text in {"DESC", "DESCRIBE"}:
        return ReferenceRole.SCHEMA_READ
    if token.token_type == TokenType.UPDATE or text == "UPDATE":
        return ReferenceRole.WRITE
    if token.token_type == TokenType.INTO or text == "INTO":
        return ReferenceRole.WRITE
    if token.token_type == TokenType.TABLE or text == "TABLE":
        if first_keyword in {"DESC", "DESCRIBE"}:
            return ReferenceRole.SCHEMA_READ
        if first_keyword == "SHOW":
            return ReferenceRole.SCHEMA_READ
        if first_keyword in {
            "CREATE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "INSERT",
            "ANALYZE",
            "OPTIMIZE",
            "RENAME",
        }:
            return ReferenceRole.WRITE
        return None
    if text == "VIEW":
        if first_keyword in {"SHOW", "DESC", "DESCRIBE"}:
            return ReferenceRole.SCHEMA_READ
        if first_keyword in {"CREATE", "DROP", "ALTER"}:
            return ReferenceRole.WRITE
    if token.token_type == TokenType.FROM or text == "FROM":
        return (
            ReferenceRole.WRITE
            if first_keyword == "DELETE" and not write_target_seen
            else ReferenceRole.DATA_READ
        )
    if token.token_type == TokenType.JOIN or text == "JOIN":
        return ReferenceRole.DATA_READ
    if text == "USING":
        return ReferenceRole.DATA_READ
    if token.token_type == TokenType.COMMA and _comma_continues_from(
        tokens, index
    ):
        return ReferenceRole.DATA_READ
    return None


def _comma_continues_from(tokens: list, comma_index: int) -> bool:
    target_depth = 0
    for token in tokens[:comma_index]:
        if token.text == "(":
            target_depth += 1
        elif token.text == ")":
            target_depth -= 1
    depth = target_depth
    boundaries = {
        "SELECT",
        "WHERE",
        "ON",
        "GROUP",
        "ORDER",
        "HAVING",
        "LIMIT",
        "WITH",
        ";",
    }
    for token in reversed(tokens[:comma_index]):
        if token.text == ")":
            depth += 1
            continue
        if token.text == "(":
            if depth == target_depth:
                return False
            depth -= 1
            continue
        if depth != target_depth:
            continue
        text = token.text.upper()
        if text in {"FROM", "JOIN"}:
            return True
        if text in boundaries:
            return False
    return False


def _analyze_statement(
    sql_text: str,
    offset: int,
    physical_local_tables: set[str],
) -> list[RelationOccurrence]:
    rename_table = re.match(
        r"^\s*RENAME\s+TABLE\s+"
        r"(?P<old>(?:`?[\w]+`?\.)?`?[\w]+`?)\s+TO\s+"
        r"(?P<new>(?:`?[\w]+`?\.)?`?[\w]+`?)",
        sql_text,
        flags=re.IGNORECASE,
    )
    if rename_table:
        occurrences = []
        for group in ("old", "new"):
            raw = rename_table.group(group)
            parts = [part.strip("`") for part in raw.split(".")]
            occurrences.append(
                RelationOccurrence(
                    parts[-2] if len(parts) >= 2 else "",
                    parts[-1],
                    ReferenceRole.WRITE,
                    offset + rename_table.start(group),
                    offset + rename_table.end(group),
                    raw,
                )
            )
        return occurrences
    show_create = re.match(
        r"^\s*SHOW\s+CREATE\s+(?:TABLE|VIEW)\s+"
        r"(?P<relation>(?:`?[\w]+`?\.)?`?[\w]+`?)",
        sql_text,
        flags=re.IGNORECASE,
    )
    if show_create:
        raw = show_create.group("relation")
        parts = [part.strip("`") for part in raw.split(".")]
        return [
            RelationOccurrence(
                parts[-2] if len(parts) >= 2 else "",
                parts[-1],
                ReferenceRole.SCHEMA_READ,
                offset + show_create.start("relation"),
                offset + show_create.end("relation"),
                raw,
            )
        ]
    tokens = Tokenizer(dialect="doris").tokenize(sql_text)
    first_keyword = _first_keyword(tokens)
    cte_names = _cte_names(sql_text)
    parsed = sqlglot.parse_one(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    schema_like = bool(
        isinstance(parsed, exp.Create)
        and next(parsed.find_all(exp.LikeProperty), None) is not None
    )
    occurrences = []
    consumed_starts = set()
    write_target_seen = False
    for index, _token in enumerate(tokens):
        role = _context_role(
            tokens,
            index,
            first_keyword,
            write_target_seen,
            schema_like,
        )
        if role is None:
            continue
        relation = _relation(tokens, index + 1)
        if relation is None:
            continue
        parts, start, end, _ = relation
        if start in consumed_starts:
            continue
        consumed_starts.add(start)
        table = parts[-1]
        database = parts[-2] if len(parts) >= 2 else ""
        physical = True
        if not database and _canonical(table) in cte_names:
            role = ReferenceRole.LOCAL
            physical = False
        elif (
            role in {ReferenceRole.DATA_READ, ReferenceRole.SCHEMA_READ}
            and _canonical(table) in physical_local_tables
        ):
            role = ReferenceRole.LOCAL
        occurrences.append(
            RelationOccurrence(
                database,
                table,
                role,
                offset + start,
                offset + end,
                sql_text[start:end],
                physical,
            )
        )
        if role is ReferenceRole.WRITE:
            write_target_seen = True
    return occurrences


def analyze_occurrences(sql_text: str) -> list[RelationOccurrence]:
    """Classify physical and local relation occurrences in raw SQL."""
    occurrences = []
    physical_local_tables = set()
    for start, end in _statement_ranges(sql_text):
        statement_sql = sql_text[start:end]
        occurrences.extend(
            _analyze_statement(
                statement_sql,
                start,
                physical_local_tables,
            )
        )
        statements = sqlglot.parse(
            statement_sql,
            dialect="doris",
            error_level=ErrorLevel.IGNORE,
        )
        statement = next(
            (item for item in statements if item is not None), None
        )
        if isinstance(statement, exp.Create):
            target = statement.this
            if isinstance(target, exp.Schema):
                target = target.this
            if isinstance(target, exp.Table):
                physical_local_tables.add(_canonical(target.name))
        elif isinstance(statement, exp.Drop) and isinstance(
            statement.this, exp.Table
        ):
            physical_local_tables.discard(_canonical(statement.this.name))
    return occurrences


def unresolved_relations(sql_text: str) -> tuple[str, ...]:
    """Return SQLGlot table nodes not classified by the token analyzer."""
    ast_tables = Counter()
    for statement in sqlglot.parse(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    ):
        if statement is None:
            continue
        ast_tables.update(
            _canonical(table.name)
            for table in statement.find_all(exp.Table)
            if table.name
        )
    for start, end in _statement_ranges(sql_text):
        statement_sql = sql_text[start:end]
        statement = sqlglot.parse_one(
            statement_sql,
            dialect="doris",
            error_level=ErrorLevel.IGNORE,
        )
        if not isinstance(statement, exp.Command):
            continue
        ast_tables.update(
            _canonical(match.group("table"))
            for match in re.finditer(
                r"(?:`?[\w]+`?\.)`?(?P<table>[\w]+)`?",
                statement_sql,
            )
        )
    classified = Counter(
        _canonical(item.table) for item in analyze_occurrences(sql_text)
    )
    unresolved = []
    for table, count in ast_tables.items():
        unresolved.extend([table] * max(0, count - classified[table]))
    return tuple(sorted(unresolved))


def _mapping_route(
    mapping: dict[str, RelationRoute],
    database: str,
    table: str,
    *,
    allow_short_name: bool,
) -> Optional[RelationRoute]:
    canonical = {_canonical(key): value for key, value in mapping.items()}
    qualified = f"{database}.{table}" if database else ""
    if qualified and _canonical(qualified) in canonical:
        return canonical[_canonical(qualified)]
    return canonical.get(_canonical(table)) if allow_short_name else None


def _contains_name(values: set[str], database: str, table: str) -> bool:
    names = {_canonical(value) for value in values}
    return _canonical(table) in names or (
        bool(database) and _canonical(f"{database}.{table}") in names
    )


def _is_project_relation(context: RewriteContext, database: str) -> bool:
    return not database or _canonical(database) in {
        _canonical(context.prod_db),
        _canonical(context.qa_db),
    }


def _route_for(
    occurrence: RelationOccurrence, context: RewriteContext
) -> Optional[RelationRoute]:
    if occurrence.role is ReferenceRole.LOCAL:
        return (
            RelationRoute(context.qa_db, occurrence.table)
            if occurrence.physical
            else None
        )
    mapping = {
        ReferenceRole.WRITE: context.write_routes,
        ReferenceRole.SCHEMA_READ: context.schema_routes,
        ReferenceRole.DATA_READ: context.data_routes,
    }.get(occurrence.role, {})
    project_relation = _is_project_relation(context, occurrence.database)
    route = _mapping_route(
        mapping,
        occurrence.database,
        occurrence.table,
        allow_short_name=project_relation,
    )
    if route is not None:
        if (
            occurrence.role is ReferenceRole.DATA_READ
            and _canonical(route.database) == _canonical(context.qa_db)
            and _contains_name(
                context.required_qa_tables,
                route.database,
                route.table,
            )
            and not _contains_name(
                context.qa_ready_tables,
                route.database,
                route.table,
            )
        ):
            job = (
                f" in job {context.current_job}" if context.current_job else ""
            )
            raise ShadowRewriteError(
                f"selected QA data source {route.table}{job} is not ready"
            )
        return route
    if not project_relation:
        return None
    if occurrence.role is ReferenceRole.WRITE:
        return RelationRoute(context.qa_db, occurrence.table)
    if occurrence.role is ReferenceRole.SCHEMA_READ:
        if _contains_name(
            context.selected_tables | context.qa_ready_tables,
            occurrence.database,
            occurrence.table,
        ):
            return RelationRoute(context.qa_db, occurrence.table)
        return RelationRoute(context.prod_db, occurrence.table)
    if occurrence.role is ReferenceRole.DATA_READ:
        if _contains_name(
            context.qa_ready_tables,
            occurrence.database,
            occurrence.table,
        ):
            return RelationRoute(context.qa_db, occurrence.table)
        if context.strict and _contains_name(
            context.selected_tables,
            occurrence.database,
            occurrence.table,
        ):
            job = (
                f" in job {context.current_job}" if context.current_job else ""
            )
            raise ShadowRewriteError(
                f"selected data source {occurrence.table}{job} has no safe route"
            )
        return RelationRoute(context.prod_db, occurrence.table)
    return None


def _quote_identifier(value: str, quote: str) -> str:
    if not quote:
        return value
    return f"{quote}{value}{quote}"


def _render_route(occurrence: RelationOccurrence, route: RelationRoute) -> str:
    quote = "`" if "`" in occurrence.raw else ""
    return (
        f"{_quote_identifier(route.database, quote)}."
        f"{_quote_identifier(route.table, quote)}"
    )


def rewrite_shadow_sql(sql_text: str, context: RewriteContext) -> str:
    """Rewrite only relation spans, preserving all other source text."""
    if not sql_text.strip():
        return ""
    replacements = []
    for occurrence in analyze_occurrences(sql_text):
        route = _route_for(occurrence, context)
        if route is None:
            continue
        replacements.append(
            (
                occurrence.start,
                occurrence.end,
                _render_route(occurrence, route),
            )
        )
    rewritten = sql_text
    for start, end, replacement in reversed(replacements):
        rewritten = f"{rewritten[:start]}{replacement}{rewritten[end:]}"
    return rewritten
