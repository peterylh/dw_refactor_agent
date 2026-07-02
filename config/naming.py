"""Naming-rule DSL loading, matching, and diagnostics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from . import core
from .semantics import (
    BUSINESS_SEMANTICS_FILE_NAME,
    business_domain_config_from_dictionaries,
    business_semantics_dictionaries,
    load_business_semantics_catalog,
)


def naming_config_path() -> Path:
    return core.PROJECT_ROOT / "naming_config.yaml"


_naming_config_cache = {}


def clear_naming_config_cache() -> None:
    _naming_config_cache.clear()


@dataclass
class TypeDef:
    label: str
    desc: str = ""
    allow: Optional[list[str]] = None
    patterns: list[str] = field(default_factory=list)
    values: Optional[list[str]] = None
    regex: Optional[str] = None
    dictionary: Optional[dict] = None
    values_from: Optional[dict] = None
    _compiled: list[re.Pattern] = field(default_factory=list)

    def __post_init__(self):
        if self.allow is None and self.values is not None:
            self.allow = self.values
        if self.regex and not self.patterns:
            self.patterns = [self.regex]
        if self.allow is not None:
            self.values = self.allow
        self.regex = self.patterns[0] if self.patterns else None
        if self.patterns and not self._compiled:
            self._compiled = [re.compile(pattern) for pattern in self.patterns]

    def validate(self, value: str) -> bool:
        matched = False
        has_validator = False
        if self.allow is not None:
            has_validator = True
            matched = value in self.allow
        if self._compiled:
            has_validator = True
            matched = matched or any(
                pattern.match(value) for pattern in self._compiled
            )
        return matched if has_validator else True


@dataclass
class LayerDef:
    templates: list
    constraints: list[dict] = field(default_factory=list)
    template_rules: list[dict] = field(default_factory=list)


@dataclass
class NamingConfig:
    types: dict[str, TypeDef]
    layers: dict[str, LayerDef]
    column_segments: list
    common_columns: set[str]
    column_templates: list = field(default_factory=list)
    column_template_rules: list[dict] = field(default_factory=list)
    table_name_max_length: Optional[int] = None
    metric_rules: dict[str, list] = field(default_factory=dict)
    metric_rule_labels: dict[str, str] = field(default_factory=dict)
    dictionaries: dict = field(default_factory=dict)
    business_domain_config: object = None

    def table_max_length_for(self, name: str, layer: str) -> Optional[int]:
        ldef = self.layers.get(layer)
        if ldef:
            for segs, constraints in zip(ldef.templates, ldef.constraints):
                max_length = constraints.get("max_length")
                if (
                    max_length is not None
                    and self._match_segments(name, segs) is not None
                ):
                    return int(max_length)
        return self.table_name_max_length

    def _match_segments(self, name: str, segments: list) -> Optional[dict]:
        def _assign(res, k, v):
            if k in res:
                if isinstance(res[k], list):
                    res[k].append(v)
                else:
                    res[k] = [res[k], v]
            else:
                res[k] = v

        """
        三段式匹配:
          1. 从左匹配固定值段（字面量 + values type）
          2. 从右匹配可选固定值段（values type）
          3. 中间剩余部分匹配 regex type（变长）
        """
        result = {}
        remaining = name
        left = 0
        right = len(segments) - 1

        # Phase 1: match literals and fixed-value types from left
        while left <= right:
            seg = segments[left]
            if seg["kind"] != "literal" and seg.get("sep_before"):
                # 有 leading separator → 不是从开头开始的段，暂停
                if seg["kind"] == "type":
                    td = self.types.get(seg["name"])
                    if td and td.allow is not None:
                        # Same as below
                        pass
                    else:
                        break
                else:
                    break
            sname = seg["name"]
            sep_before = seg.get("sep_before", "")
            sep_after = seg.get("sep_after", "")

            if not remaining.startswith(sep_before):
                if seg.get("optional", False):
                    left += 1
                    continue
                return None
            rest = remaining[len(sep_before) :]

            if seg["kind"] == "literal":
                if not rest.startswith(sname):
                    if seg.get("optional", False):
                        left += 1
                        continue
                    return None
                remaining = rest[len(sname) :]
                if sep_after:
                    if not remaining.startswith(sep_after):
                        if seg.get("optional", False):
                            left += 1
                            continue
                        return None
                    remaining = remaining[len(sep_after) :]
                left += 1

            elif seg["kind"] == "type":
                td = self.types.get(sname)
                if td and td.allow is not None:
                    matched = None
                    for v in sorted(td.allow, key=len, reverse=True):
                        core = str(v)
                        if rest.startswith(core):
                            after = rest[len(core) :]
                            if sep_after:
                                if not after.startswith(sep_after):
                                    continue
                                after = after[len(sep_after) :]
                            matched = v
                            remaining = after
                            break
                    if matched is not None:
                        result[sname] = matched
                        left += 1
                    elif td.patterns:
                        break
                    elif seg.get("optional", False):
                        left += 1
                    else:
                        return None
                else:
                    # 遇到 regex type，暂停 left 匹配
                    break

        # Phase 2: match trailing types with values from right
        # 匹配 _type-value 模式（包括独立 _ 字面量 + 紧跟的 values type）
        while right >= left:
            seg = segments[right]
            sname = seg["name"]
            td = self.types.get(sname)
            has_values = td and td.allow is not None

            if not has_values:
                break  # 只有 values type 能从右侧匹配

            sep_before = seg.get("sep_before", "")
            check_prefix = "" if seg.get("concat_left") else sep_before or "_"
            matched = None
            for v in sorted(td.allow, key=len, reverse=True):
                suffix = check_prefix + str(v)
                if remaining.endswith(suffix):
                    # 如果是独立 _，前一段应该是 _ 字面量，一并跳过
                    if (
                        not sep_before
                        and not seg.get("concat_left")
                        and right > left
                    ):
                        prev = segments[right - 1]
                        if prev["kind"] == "literal" and prev["name"] == "_":
                            right -= 1  # skip the _ literal
                    matched = v
                    remaining = remaining[: -len(suffix)]
                    break
            if matched is not None:
                result[sname] = matched
                right -= 1
            elif seg.get("optional", False):
                right -= 1
            else:
                break

        # Phase 3: match remaining middle segments left-to-right
        while left <= right:
            seg = segments[left]
            sname = seg["name"]
            sep_before = seg.get("sep_before", "")
            sep_after = seg.get("sep_after", "")
            optional = seg.get("optional", False)

            if not remaining.startswith(sep_before):
                if optional:
                    left += 1
                    continue
                return None
            rest = remaining[len(sep_before) :]

            if seg["kind"] == "literal":
                if not rest.startswith(sname):
                    if optional:
                        left += 1
                        continue
                    return None
                remaining = rest[len(sname) :]
                left += 1

            elif seg["kind"] == "type":
                td = self.types.get(sname)
                if td and td.allow is not None:
                    matched = None
                    for v in sorted(td.allow, key=len, reverse=True):
                        if rest.startswith(v):
                            matched = v
                            remaining = rest[len(v) :]
                            break
                    if matched is not None:
                        _assign(result, sname, matched)
                        left += 1
                        continue
                    if not td.patterns:
                        if optional:
                            left += 1
                            continue
                        return None

                if td and td.patterns:
                    # 判断 regex 是否允许下划线
                    allows_underscore = any(
                        "_" in pattern for pattern in td.patterns
                    )
                    if allows_underscore:
                        # 变长 type：消耗到下一个段之前
                        if left + 1 <= right and not optional:
                            # 后面还有段，找下一个段需要的前缀
                            next_seg = segments[left + 1]
                            if next_seg["kind"] == "literal":
                                idx = rest.rfind(next_seg["name"])
                                if idx >= 0:
                                    candidate = rest[:idx]
                                    if td.validate(candidate):
                                        _assign(result, sname, candidate)
                                        remaining = rest[idx:]
                                        left += 1
                                        continue
                            # fallback: 消耗全部
                            if td.validate(rest) and rest:
                                _assign(result, sname, rest)
                                remaining = ""
                                left += 1
                            else:
                                return None
                        else:
                            if td.validate(rest) and rest:
                                _assign(result, sname, rest)
                                remaining = ""
                                left += 1
                            else:
                                return None
                    else:
                        # 定长 regex（如 source: 不含 _）→ 按 _ 切分
                        idx = rest.find("_")
                        if idx >= 0:
                            candidate = rest[:idx]
                            if td.validate(candidate):
                                _assign(result, sname, candidate)
                                remaining = rest[idx:]
                                left += 1
                                continue
                        if td.validate(rest) and rest:
                            _assign(result, sname, rest)
                            remaining = ""
                            left += 1
                        else:
                            return None
                else:
                    if optional:
                        left += 1
                    else:
                        return None

        return result if not remaining else None

    def _assign_match_value(self, result: dict, key: str, value):
        if key in result:
            if isinstance(result[key], list):
                if isinstance(value, list):
                    result[key].extend(value)
                else:
                    result[key].append(value)
            else:
                if isinstance(value, list):
                    result[key] = [result[key], *value]
                else:
                    result[key] = [result[key], value]
        else:
            result[key] = value

    def _merge_match_dict(self, base: dict, extra: dict) -> dict:
        merged = dict(base)
        for key, value in extra.items():
            self._assign_match_value(merged, key, value)
        return merged

    def _match_metric_rule_impl(
        self,
        name: str,
        rule_name: str,
        active_rules: tuple[str, ...],
    ) -> Optional[dict]:
        if rule_name in active_rules:
            return None

        rule_defs = self.metric_rules.get(rule_name, [])
        for rule_def in rule_defs:
            kind = rule_def.get("kind")
            if kind == "segments":
                matched = self._match_segments(name, rule_def["template"])
            elif kind == "sequence":
                matched = self._match_metric_sequence(
                    name,
                    rule_def["nodes"],
                    active_rules + (rule_name,),
                )
            else:
                matched = None

            if matched is not None:
                return matched
        return None

    def _match_metric_sequence(
        self,
        name: str,
        nodes: list[dict],
        active_rules: tuple[str, ...],
    ) -> Optional[dict]:
        parts = name.split("_")
        if not parts or any(not part for part in parts):
            return None

        memo: dict[tuple[int, int], Optional[dict]] = {}

        def visit(node_idx: int, part_idx: int) -> Optional[dict]:
            key = (node_idx, part_idx)
            if key in memo:
                return memo[key]

            if node_idx == len(nodes):
                result = {} if part_idx == len(parts) else None
                memo[key] = result
                return result

            node = nodes[node_idx]
            repeat = node.get("repeat", {"min": 1, "max": 1})
            min_repeat = int(repeat.get("min", 1))
            max_repeat = repeat.get("max")
            max_repeat = int(max_repeat) if max_repeat is not None else None

            def consume(
                current_idx: int,
                consumed: int,
                acc: dict,
            ) -> Optional[dict]:
                if consumed >= min_repeat:
                    tail = visit(node_idx + 1, current_idx)
                    if tail is not None:
                        return self._merge_match_dict(acc, tail)

                if current_idx >= len(parts):
                    return None
                if max_repeat is not None and consumed >= max_repeat:
                    return None

                for end in range(current_idx + 1, len(parts) + 1):
                    candidate = "_".join(parts[current_idx:end])
                    item_match = self._match_metric_item(
                        candidate,
                        node,
                        active_rules,
                    )
                    if item_match is None:
                        continue
                    merged = self._merge_match_dict(acc, item_match)
                    result = consume(end, consumed + 1, merged)
                    if result is not None:
                        return result
                return None

            result = consume(part_idx, 0, {})
            memo[key] = result
            return result

        return visit(0, 0)

    def _match_metric_item(
        self,
        candidate: str,
        node: dict,
        active_rules: tuple[str, ...],
    ) -> Optional[dict]:
        kind = node.get("kind")
        if kind == "literal":
            if candidate == node["name"]:
                return {}
            return None

        if kind == "type":
            type_def = self.types.get(node["name"])
            if type_def and type_def.validate(candidate):
                return {node["name"]: candidate}
            return None

        if kind == "rule":
            return self._match_metric_rule_impl(
                candidate,
                node["name"],
                active_rules,
            )

        return None

    def match_metric_rule(self, name: str, rule_name: str) -> Optional[dict]:
        return self._match_metric_rule_impl(name, rule_name, ())

    def _metric_rule_name_for_kind(
        self,
        metric_kind: str | None,
    ) -> str | None:
        if metric_kind is None:
            return None
        kind = str(metric_kind).strip()
        if not kind:
            return None
        normalized = kind.lower()
        aliases = {
            "atomic": ("atomic", "atomic_metrics"),
            "atomic_metrics": ("atomic_metrics", "atomic"),
            "derived": ("derived", "derived_metrics"),
            "derived_metrics": ("derived_metrics", "derived"),
        }
        for candidate in aliases.get(normalized, (kind, f"{kind}_metrics")):
            if self.metric_rules.get(candidate):
                return candidate
        return None

    def _metric_rule_label_for_name(self, rule_name: str) -> str:
        return self.metric_rule_labels.get(rule_name, rule_name)

    def _metric_node_expected(self, node: dict) -> dict:
        expected = dict(node)
        type_name = node.get("name") if node.get("kind") == "type" else ""
        if type_name:
            expected["type"] = self._type_def_info(type_name)
        return expected

    def diagnose_metric_name(
        self,
        name: str,
        metric_kind: str | None = None,
        rule_name: str | None = None,
    ) -> dict:
        metric_kind_text = (
            str(metric_kind).strip() if metric_kind is not None else None
        )
        resolved_rule_name = (
            str(rule_name).strip()
            if rule_name
            else self._metric_rule_name_for_kind(metric_kind_text)
        )
        if not resolved_rule_name:
            return {
                "actual": name,
                "metric_kind": metric_kind_text,
                "rule_name": None,
                "passed": False,
                "attempts": [],
                "failure": {
                    "code": "unknown_metric_kind",
                    "actual": metric_kind_text,
                },
            }

        attempts = []
        for rule_def in self.metric_rules.get(resolved_rule_name, []):
            kind = rule_def.get("kind")
            if kind == "segments":
                attempts.append(
                    self.diagnose_segments(
                        name,
                        rule_def["template"],
                        {
                            "name": resolved_rule_name,
                            "description": (
                                self._metric_rule_label_for_name(
                                    resolved_rule_name
                                )
                            ),
                            "raw_expr": rule_def.get("raw_expr"),
                            "constraints": {},
                        },
                    )
                )
                continue

            if kind == "sequence":
                matched = self._match_metric_sequence(
                    name,
                    rule_def["nodes"],
                    (),
                )
                attempt = {
                    "actual": name,
                    "passed": matched is not None,
                    "rule": {
                        "name": resolved_rule_name,
                        "description": self._metric_rule_label_for_name(
                            resolved_rule_name
                        ),
                        "raw_expr": rule_def.get("raw_expr"),
                        "constraints": {},
                    },
                    "nodes": [
                        self._metric_node_expected(node)
                        for node in rule_def.get("nodes") or []
                    ],
                }
                if matched is not None:
                    attempt["matched_values"] = matched
                else:
                    attempt["failure"] = {
                        "code": "metric_sequence_mismatch",
                        "expected": attempt["nodes"],
                        "actual": name,
                    }
                attempts.append(attempt)
                continue

            attempts.append(
                {
                    "actual": name,
                    "passed": False,
                    "rule": {"name": resolved_rule_name},
                    "failure": {
                        "code": "unsupported_metric_rule_kind",
                        "actual": kind,
                    },
                }
            )

        if not attempts:
            return {
                "actual": name,
                "metric_kind": metric_kind_text,
                "rule_name": resolved_rule_name,
                "passed": False,
                "attempts": [],
                "failure": {
                    "code": "unknown_metric_rule",
                    "actual": resolved_rule_name,
                },
            }

        return {
            "actual": name,
            "metric_kind": metric_kind_text,
            "rule_name": resolved_rule_name,
            "passed": any(attempt.get("passed") for attempt in attempts),
            "attempts": attempts,
        }

    def _type_def_info(self, type_name: str) -> dict:
        type_def = self.types.get(type_name)
        if not type_def:
            return {"name": type_name}
        return {
            "name": type_name,
            "label": type_def.label,
            "description": type_def.desc,
            "allow": list(type_def.allow)
            if type_def.allow is not None
            else None,
            "patterns": list(type_def.patterns),
            "dictionary": type_def.dictionary,
            "values_from": type_def.values_from,
        }

    def explain_segment(
        self, segment: dict, position: int | None = None
    ) -> dict:
        info = {
            "position": position,
            "kind": segment.get("kind"),
            "name": segment.get("name"),
            "optional": bool(segment.get("optional", False)),
            "sep_before": segment.get("sep_before", ""),
            "sep_after": segment.get("sep_after", ""),
            "concat_left": bool(segment.get("concat_left", False)),
        }
        if segment.get("kind") == "type":
            info["type"] = self._type_def_info(segment.get("name", ""))
        return info

    def explain_segments(self, segments: list) -> list[dict]:
        return [
            self.explain_segment(segment, idx + 1)
            for idx, segment in enumerate(segments)
        ]

    def expression_text(self, segments: list) -> str:
        text = ""
        for segment in segments:
            name = segment.get("name", "")
            token = (
                f"{{{name}}}" if segment.get("kind") == "type" else str(name)
            )
            if segment.get("optional"):
                token += "?"
            token = (
                f"{segment.get('sep_before', '')}"
                f"{token}"
                f"{segment.get('sep_after', '')}"
            )

            if (
                not text
                or segment.get("concat_left")
                or token.startswith("_")
                or text.endswith("_")
            ):
                text += token
            else:
                text += f" {token}"
        return text

    def _candidate_for_type(
        self,
        rest: str,
        segments: list,
        index: int,
        type_def: TypeDef,
    ) -> str:
        if not rest:
            return ""

        allows_underscore = any(
            "_" in pattern for pattern in type_def.patterns
        )
        if allows_underscore and index + 1 < len(segments):
            next_seg = segments[index + 1]
            if next_seg.get("kind") == "literal":
                marker = str(next_seg.get("name", ""))
                marker_idx = rest.rfind(marker) if marker else -1
                if marker_idx > 0:
                    return rest[:marker_idx]

        if not allows_underscore:
            sep_idx = rest.find("_")
            if sep_idx > 0:
                return rest[:sep_idx]

        return rest

    def _locate_segment_failure(self, name: str, segments: list) -> dict:
        remaining = str(name or "")
        consumed = 0

        for idx, segment in enumerate(segments):
            sep_before = segment.get("sep_before", "")
            sep_after = segment.get("sep_after", "")
            optional = bool(segment.get("optional", False))
            info = self.explain_segment(segment, idx + 1)

            if sep_before and not remaining.startswith(sep_before):
                if optional:
                    continue
                return {
                    "code": "separator_mismatch",
                    "position": idx + 1,
                    "segment": info,
                    "expected": sep_before,
                    "actual_remaining": remaining,
                    "consumed_chars": consumed,
                }

            rest = remaining[len(sep_before) :]
            consumed += len(sep_before)

            if segment.get("kind") == "literal":
                literal = str(segment.get("name", ""))
                if rest.startswith(literal):
                    remaining = rest[len(literal) :]
                    consumed += len(literal)
                    if sep_after and remaining.startswith(sep_after):
                        remaining = remaining[len(sep_after) :]
                        consumed += len(sep_after)
                    continue
                if optional:
                    consumed -= len(sep_before)
                    continue
                return {
                    "code": "literal_mismatch",
                    "position": idx + 1,
                    "segment": info,
                    "expected": literal,
                    "actual_remaining": rest,
                    "consumed_chars": consumed,
                }

            if segment.get("kind") != "type":
                if optional:
                    consumed -= len(sep_before)
                    continue
                return {
                    "code": "unsupported_segment_kind",
                    "position": idx + 1,
                    "segment": info,
                    "actual_remaining": rest,
                    "consumed_chars": consumed,
                }

            type_name = segment.get("name", "")
            type_def = self.types.get(type_name)
            if not type_def:
                return {
                    "code": "unknown_type",
                    "position": idx + 1,
                    "segment": info,
                    "actual_remaining": rest,
                    "consumed_chars": consumed,
                }

            if type_def.allow is not None:
                matched = None
                for value in sorted(type_def.allow, key=len, reverse=True):
                    value = str(value)
                    if rest.startswith(value):
                        matched = value
                        break
                if matched is not None:
                    remaining = rest[len(matched) :]
                    consumed += len(matched)
                    if sep_after and remaining.startswith(sep_after):
                        remaining = remaining[len(sep_after) :]
                        consumed += len(sep_after)
                    continue
                if not type_def.patterns:
                    if optional:
                        consumed -= len(sep_before)
                        continue
                    return {
                        "code": "allowed_values_mismatch",
                        "position": idx + 1,
                        "segment": info,
                        "expected": list(type_def.allow),
                        "actual_remaining": rest,
                        "consumed_chars": consumed,
                    }

            if type_def.patterns:
                candidate = self._candidate_for_type(
                    rest, segments, idx, type_def
                )
                if candidate and type_def.validate(candidate):
                    remaining = rest[len(candidate) :]
                    consumed += len(candidate)
                    if sep_after and remaining.startswith(sep_after):
                        remaining = remaining[len(sep_after) :]
                        consumed += len(sep_after)
                    continue
                if optional:
                    consumed -= len(sep_before)
                    continue
                return {
                    "code": "type_pattern_mismatch",
                    "position": idx + 1,
                    "segment": info,
                    "expected": list(type_def.patterns),
                    "actual": candidate or rest,
                    "actual_remaining": rest,
                    "consumed_chars": consumed,
                }

            remaining = ""
            consumed = len(str(name or ""))

        if remaining:
            return {
                "code": "trailing_text",
                "position": len(segments) + 1,
                "expected": "end_of_name",
                "actual_remaining": remaining,
                "consumed_chars": consumed,
            }

        return {
            "code": "match_failed",
            "actual_remaining": remaining,
            "consumed_chars": consumed,
        }

    def diagnose_segments(
        self,
        name: str,
        segments: list,
        rule: dict | None = None,
    ) -> dict:
        matched = self._match_segments(name, segments)
        diagnostic = {
            "actual": name,
            "passed": matched is not None,
            "rule": rule or {},
            "expression": self.expression_text(segments),
            "segments": self.explain_segments(segments),
        }
        if matched is not None:
            diagnostic["matched_values"] = matched
            return diagnostic

        diagnostic["failure"] = self._locate_segment_failure(name, segments)
        return diagnostic

    def _model_path_values(self, model: dict, path: str) -> list[str]:
        values = [model]
        for part in str(path or "").split("."):
            next_values = []
            for value in values:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and part in item:
                            next_values.append(item[part])
                elif isinstance(value, dict) and part in value:
                    next_values.append(value[part])
            values = next_values

        result = []
        seen = set()

        def collect(value) -> None:
            if isinstance(value, list):
                for item in value:
                    collect(item)
                return
            if value is None:
                return
            text = str(value)
            if not text or text in seen:
                return
            seen.add(text)
            result.append(text)

        for value in values:
            collect(value)
        return result

    @staticmethod
    def _dedupe_text_values(values: list) -> list[str]:
        result = []
        seen = set()
        for value in values:
            if value is None:
                continue
            text = str(value)
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _primary_model_entity_values(self, model: dict) -> list[str]:
        values = []
        entities = model.get("entities")
        if isinstance(entities, dict):
            entities = [entities]
        if isinstance(entities, list):
            for entity in entities:
                if (
                    isinstance(entity, dict)
                    and entity.get("type") == "primary"
                ):
                    values.append(entity.get("code"))

        legacy_entity = model.get("entity")
        if isinstance(legacy_entity, dict):
            values.append(legacy_entity.get("code"))
        return self._dedupe_text_values(values)

    def _model_values_for_type(
        self, model: dict, type_name: str, values_from: dict
    ) -> list[str]:
        if type_name == "MODEL_ENTITY":
            return self._primary_model_entity_values(model)

        result = []
        seen = set()
        for path in values_from.get("paths") or []:
            for value in self._model_path_values(model, path):
                if value in seen:
                    continue
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _matched_values_as_list(value) -> list[str]:
        raw_values = value if isinstance(value, list) else [value]
        return [str(item) for item in raw_values if item is not None]

    def _attach_model_constraints(
        self,
        attempt: dict,
        model: dict,
    ) -> dict:
        if not attempt.get("passed") or not attempt.get("matched_values"):
            return attempt

        constraints = {}
        matched_values = attempt.get("matched_values") or {}
        for type_name, value in matched_values.items():
            type_def = self.types.get(type_name)
            values_from = type_def.values_from if type_def else None
            if not values_from or values_from.get("scope") != "current_model":
                continue

            allowed_values = self._model_values_for_type(
                model, type_name, values_from
            )
            actual_values = self._matched_values_as_list(value)
            constraint = {
                "values_from": values_from,
                "allowed_values_from_model": allowed_values,
                "actual_values": actual_values,
            }
            if allowed_values and set(actual_values).issubset(
                set(allowed_values)
            ):
                constraint["matched_model_value"] = True
            else:
                constraint["matched_model_value"] = False
                if allowed_values:
                    constraint["model_value_failure"] = {
                        "code": "model_value_mismatch",
                        "actual": actual_values,
                        "expected": allowed_values,
                    }
                else:
                    constraint["model_value_failure"] = {
                        "code": "missing_model_values",
                        "paths": list(values_from.get("paths") or []),
                    }
            constraints[type_name] = constraint

        if not constraints:
            return attempt

        attempt["model_constraints"] = constraints
        attempt["passed"] = attempt.get("passed") and all(
            constraint.get("matched_model_value")
            for constraint in constraints.values()
        )
        return attempt

    def diagnose_table_name(self, name: str, model: dict | None) -> dict:
        model_data = model if isinstance(model, dict) else {}
        layer = model_data.get("layer")
        model_name = model_data.get("name")
        if not layer:
            return {
                "actual": name,
                "layer": None,
                "layer_source": "model",
                "model_name": model_name,
                "passed": False,
                "attempts": [],
                "failure": {
                    "code": "missing_model_layer",
                    "message": (
                        "model.layer is required to diagnose table name"
                    ),
                },
            }

        layer_def = self.layers.get(layer)
        if not layer_def:
            return {
                "actual": name,
                "layer": layer,
                "layer_source": "model",
                "model_name": model_name,
                "passed": False,
                "attempts": [],
                "failure": {
                    "code": "unknown_model_layer",
                    "message": ("model.layer is not defined in naming config"),
                },
            }

        attempts = []
        rules = layer_def.template_rules or [{} for _ in layer_def.templates]
        for segments, rule in zip(layer_def.templates, rules):
            attempt = self.diagnose_segments(name, segments, rule)
            attempt["template_passed"] = bool(attempt.get("passed"))
            attempts.append(
                self._attach_model_constraints(attempt, model_data)
            )

        return {
            "actual": name,
            "layer": layer,
            "layer_source": "model",
            "model_name": model_name,
            "passed": any(attempt.get("passed") for attempt in attempts),
            "attempts": attempts,
        }

    def diagnose_column_name(self, name: str) -> dict:
        if name in self.common_columns:
            return {
                "actual": name,
                "passed": True,
                "common_column": True,
                "attempts": [],
            }

        templates = self.column_templates or (
            [self.column_segments] if self.column_segments else []
        )
        rules = self.column_template_rules or [{} for _ in templates]
        attempts = [
            self.diagnose_segments(name, segments, rule)
            for segments, rule in zip(templates, rules)
        ]
        return {
            "actual": name,
            "passed": any(attempt.get("passed") for attempt in attempts),
            "common_column": False,
            "attempts": attempts,
        }


_REPEAT_RE = re.compile(r"^(?P<name>.+)\{(?P<min>\d+),(?P<max>\d*)\}$")


def _split_repeat_suffix(raw: str) -> tuple[str, dict, bool]:
    if raw.endswith("?"):
        return raw[:-1], {"min": 0, "max": 1}, True

    match = _REPEAT_RE.match(raw)
    if match:
        max_value = match.group("max")
        return (
            match.group("name"),
            {
                "min": int(match.group("min")),
                "max": int(max_value) if max_value else None,
            },
            False,
        )

    return raw, {"min": 1, "max": 1}, False


def _expand_repeat_segment_item(item) -> list[list]:
    raw_str, _forced_concat_left = _raw_segment_item(item)
    raw_str = str(raw_str)
    sigil = ""
    name = raw_str
    if raw_str.startswith("$"):
        sigil = "$"
        name = raw_str[1:]

    match = _REPEAT_RE.match(name)
    if not match:
        return [[item]]

    max_value = match.group("max")
    if max_value == "":
        raise ValueError(
            "Segment naming rules require finite {min,max} repeat syntax"
        )

    min_repeat = int(match.group("min"))
    max_repeat = int(max_value)
    if min_repeat > max_repeat:
        raise ValueError(
            "Segment naming rule repeat min must be less than or equal to max"
        )

    base_name = match.group("name")
    variants = []
    for count in range(max_repeat, min_repeat - 1, -1):
        repeated = []
        for idx in range(count):
            repeat_sigil = sigil if idx == 0 else ("$" if sigil else "")
            token = repeat_sigil + base_name
            if idx == 0 and isinstance(item, dict):
                repeated.append({**item, "token": token})
            else:
                repeated.append(token)
        variants.append(repeated)
    return variants


def _expand_rule_expr_repeats(expr) -> list:
    if not isinstance(expr, list):
        return [expr]

    variants = [[]]
    for part in expr:
        if isinstance(part, list):
            choices = [
                [variant] for variant in _expand_rule_expr_repeats(part)
            ]
        else:
            choices = _expand_repeat_segment_item(part)

        variants = [base + choice for base in variants for choice in choices]
    return variants


def _raw_segment_item(item) -> tuple[str, bool]:
    if isinstance(item, dict) and "token" in item:
        return str(item["token"]), bool(item.get("concat_left", False))
    return str(item), False


def _parse_segments(raw: list, _types: dict) -> list:
    """
    解析列表格式的 segments。

    [ods, $source, $entity, $load_type]
      → ods 是常量, $source 是变量, 段间自动用 _ 连接

    规则:
      - $name  → 变量（从 types 中查找）
      - $name? → 可选变量
      - 其他   → 常量字面量
    """
    parsed = []
    for item in raw:
        raw_str, forced_concat_left = _raw_segment_item(item)
        is_type = False
        concat_left = forced_concat_left

        if raw_str.startswith("$+"):
            raise ValueError(
                "The $+TYPE syntax is not supported; use nested ['', ...] "
                "expressions for direct concatenation"
            )

        if raw_str.startswith("$"):
            is_type = True
            raw_str = raw_str[1:]

        raw_str, _, optional = _split_repeat_suffix(raw_str)

        if is_type:
            parsed.append(
                {
                    "name": raw_str,
                    "kind": "type",
                    "optional": optional,
                    "sep_before": "",
                    "sep_after": "",
                    "concat_left": concat_left,
                }
            )
        else:
            parsed.append(
                {
                    "name": raw_str,
                    "kind": "literal",
                    "optional": optional,
                    "sep_before": "",
                    "sep_after": "",
                    "concat_left": concat_left,
                }
            )

    i = 0
    while i < len(parsed) - 1:
        left = parsed[i]
        right = parsed[i + 1]
        if right.get("concat_left"):
            pass
        elif right["optional"]:
            right["sep_before"] = "_" + right["sep_before"]
        elif left["optional"]:
            left["sep_after"] = left["sep_after"] + "_"
        else:
            literal = {
                "name": "_",
                "kind": "literal",
                "optional": False,
                "sep_before": "",
                "sep_after": "",
                "concat_left": False,
            }
            parsed.insert(i + 1, literal)
            i += 1
        i += 1
    return parsed


def _split_join_expression(expr) -> tuple[str, list]:
    if isinstance(expr, list):
        if expr and isinstance(expr[0], str) and expr[0] in ("", "_"):
            return expr[0], expr[1:]
        return "_", expr
    return "_", [expr]


def _mark_concat_left(items: list) -> list:
    if not items:
        return []
    first, *rest = items
    if isinstance(first, dict):
        first = {**first, "concat_left": True}
    else:
        first = {"token": first, "concat_left": True}
    return [first, *rest]


def _expr_to_segment_items(expr) -> list:
    separator, parts = _split_join_expression(expr)
    items = []
    for part in parts:
        part_items = (
            _expr_to_segment_items(part) if isinstance(part, list) else [part]
        )
        if items and separator == "":
            part_items = _mark_concat_left(part_items)
        items.extend(part_items)
    return items


def _parse_rule_expression(expr, types: dict) -> list:
    return _parse_segments(_expr_to_segment_items(expr), types)


_TEMPLATE_REPEAT_PREFIX_RE = re.compile(r"^\{\d+,\d*\}")


def _template_to_segment_items(template) -> list:
    if isinstance(template, list):
        return template

    raw = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.find("}", i)
            if j == -1:
                raise ValueError(
                    f"Unclosed type placeholder in naming template: {template!r}"
                )
            content = template[i + 1 : j]
            i = j + 1
            repeat_match = _TEMPLATE_REPEAT_PREFIX_RE.match(template[i:])
            repeat_suffix = ""
            if repeat_match:
                repeat_suffix = repeat_match.group(0)
                i += len(repeat_suffix)
            raw.append("$" + content + repeat_suffix)
        else:
            j = template.find("{", i)
            if j == -1:
                raw.append(template[i:])
                break
            if j > i:
                raw.append(template[i:j])
            i = j
    return raw


def _parse_template(template, types: dict) -> list:
    """支持列表或字符串格式。"""
    return _parse_segments(_template_to_segment_items(template), types)


def _parse_template_variants(template, types: dict) -> list[list]:
    return [
        _parse_segments(template_variant, types)
        for template_variant in _expand_rule_expr_repeats(
            _template_to_segment_items(template)
        )
    ]


def _parse_explicit_pattern(template: str, _types: dict) -> list:
    """解析显式分隔符字符串，不自动补充下划线。"""
    parsed = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.find("}", i)
            if j == -1:
                parsed.append(template[i:])
                break
            name = template[i + 1 : j]
            optional = name.endswith("?")
            if optional:
                name = name[:-1]
            parsed.append(
                {
                    "name": name,
                    "kind": "type",
                    "optional": optional,
                    "sep_before": "",
                    "sep_after": "",
                    "concat_left": False,
                }
            )
            i = j + 1
            continue

        j = template.find("{", i)
        literal = template[i:] if j == -1 else template[i:j]
        if literal:
            parsed.append(
                {
                    "name": literal,
                    "kind": "literal",
                    "optional": False,
                    "sep_before": "",
                    "sep_after": "",
                    "concat_left": False,
                }
            )
        if j == -1:
            break
        i = j
    return parsed


def _normalize_metric_repeat(repeat) -> dict:
    if repeat is None:
        return {"min": 1, "max": 1}
    if isinstance(repeat, int):
        return {"min": repeat, "max": repeat}
    if isinstance(repeat, str):
        raw, parsed, changed = _split_repeat_suffix(repeat)
        if changed and not raw:
            return parsed
    if isinstance(repeat, dict):
        return {
            "min": int(repeat.get("min", 1)),
            "max": (
                int(repeat["max"]) if repeat.get("max") is not None else None
            ),
        }
    raise ValueError(f"Unsupported metric repeat config: {repeat!r}")


def _parse_metric_sequence_item(item: dict | str) -> dict:
    if isinstance(item, str):
        if item.endswith(("+", "*")):
            raise ValueError(
                "Use {min,max} repeat syntax instead of '+' or '*' in metric rules"
            )
        raw, repeat, _ = _split_repeat_suffix(item)

        if raw.startswith("$"):
            return {
                "kind": "type",
                "name": raw[1:],
                "repeat": repeat,
            }
        if raw.startswith("@"):
            return {
                "kind": "rule",
                "name": raw[1:],
                "repeat": repeat,
            }
        return {
            "kind": "literal",
            "name": raw,
            "repeat": repeat,
        }

    if "type" in item:
        kind = "type"
        name = str(item["type"])
    elif "rule" in item:
        kind = "rule"
        name = str(item["rule"])
    elif "literal" in item:
        kind = "literal"
        name = str(item["literal"])
    else:
        raise ValueError(
            f"Metric sequence item must define type/rule/literal: {item!r}"
        )

    return {
        "kind": kind,
        "name": name,
        "repeat": _normalize_metric_repeat(item.get("repeat")),
    }


def _parse_metric_sequence(sequence: list) -> dict:
    separator, sequence = _split_join_expression(sequence)
    if separator != "_":
        raise ValueError(
            "Metric rules currently require '_' as the join separator"
        )
    return {
        "kind": "sequence",
        "nodes": [_parse_metric_sequence_item(item) for item in sequence],
    }


def _parse_metric_rule_defs(rule_cfg, types: dict) -> list[dict]:
    if isinstance(rule_cfg, dict) and "sequence" in rule_cfg:
        return [_parse_metric_sequence(rule_cfg.get("sequence") or [])]

    parser = _parse_template
    if isinstance(rule_cfg, dict):
        if (
            isinstance(rule_cfg.get("pattern"), str)
            and "templates" not in rule_cfg
            and "segments" not in rule_cfg
        ):
            parser = _parse_explicit_pattern
            template_defs = rule_cfg.get("pattern") or []
        else:
            template_defs = (
                rule_cfg.get("templates") or rule_cfg.get("segments") or []
            )
    else:
        template_defs = rule_cfg

    if isinstance(template_defs, str) or (
        isinstance(template_defs, list)
        and template_defs
        and isinstance(template_defs[0], str)
    ):
        template_defs = [template_defs]

    return [
        {"kind": "segments", "template": parser(template, types)}
        for template in template_defs
    ]


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _rule_name(ref) -> str:
    raw = str(ref)
    return raw[1:] if raw.startswith("@") else raw


def _rule_cfg(rule_defs: dict, ref):
    name = _rule_name(ref)
    if name not in rule_defs:
        raise ValueError(f"Unknown naming rule reference: @{name}")
    return rule_defs[name]


def _rule_expr(rule_defs: dict, ref):
    cfg = _rule_cfg(rule_defs, ref)
    if isinstance(cfg, dict) and "expr" in cfg:
        return cfg["expr"]
    return cfg


def _rule_constraints(rule_defs: dict, ref) -> dict:
    cfg = _rule_cfg(rule_defs, ref)
    if isinstance(cfg, dict):
        return cfg.get("constraints") or {}
    return {}


def _rule_desc(rule_defs: dict, ref) -> str:
    cfg = _rule_cfg(rule_defs, ref)
    if isinstance(cfg, dict):
        return str(cfg.get("desc") or "").strip()
    return ""


def _compile_rule_expr_as_segment_templates(
    rule_defs: dict,
    ref,
    types: dict,
) -> list[list]:
    expr = _rule_expr(rule_defs, ref)
    if isinstance(expr, str):
        return _parse_template_variants(expr, types)
    return [
        _parse_rule_expression(expr_variant, types)
        for expr_variant in _expand_rule_expr_repeats(expr)
    ]


def _compile_rule_expr_as_metric(rule_defs: dict, ref) -> dict:
    return _parse_metric_sequence(_rule_expr(rule_defs, ref))


def _compile_table_bindings(
    table_bindings: dict,
    rule_defs: dict,
    types: dict,
) -> tuple[dict[str, LayerDef], Optional[int]]:
    layers = {}
    max_lengths = []
    for layer_name, refs in table_bindings.items():
        templates = []
        constraints_list = []
        template_rules = []
        for ref in _as_list(refs):
            compiled_templates = _compile_rule_expr_as_segment_templates(
                rule_defs,
                ref,
                types,
            )
            templates.extend(compiled_templates)
            constraints = _rule_constraints(rule_defs, ref)
            constraints_list.extend([constraints] * len(compiled_templates))
            rule_info = {
                "name": _rule_name(ref),
                "description": _rule_desc(rule_defs, ref),
                "raw_expr": _rule_expr(rule_defs, ref),
                "constraints": constraints,
            }
            template_rules.extend([rule_info] * len(compiled_templates))
            if constraints.get("max_length") is not None:
                max_lengths.append(int(constraints["max_length"]))
        layers[layer_name] = LayerDef(
            templates=templates,
            constraints=constraints_list,
            template_rules=template_rules,
        )

    table_name_max_length = min(max_lengths) if max_lengths else None
    return layers, table_name_max_length


def _compile_column_bindings(
    column_binding: dict,
    rule_defs: dict,
    types: dict,
) -> tuple[list, list, list, set[str]]:
    column_templates = []
    column_template_rules = []
    for ref in _as_list(column_binding.get("rules")):
        compiled_templates = _compile_rule_expr_as_segment_templates(
            rule_defs,
            ref,
            types,
        )
        column_templates.extend(compiled_templates)
        rule_info = {
            "name": _rule_name(ref),
            "description": _rule_desc(rule_defs, ref),
            "raw_expr": _rule_expr(rule_defs, ref),
            "constraints": _rule_constraints(rule_defs, ref),
        }
        column_template_rules.extend([rule_info] * len(compiled_templates))
    column_segments = column_templates[0] if column_templates else []
    common_columns = set(column_binding.get("allow", []))
    return (
        column_segments,
        column_templates,
        column_template_rules,
        common_columns,
    )


def _compile_metric_bindings(
    metric_binding: dict,
    rule_defs: dict,
) -> tuple[dict, dict]:
    metric_rules = {}
    metric_rule_labels = {}
    for binding_name, ref in metric_binding.items():
        rule_name = _rule_name(ref)
        compiled = [_compile_rule_expr_as_metric(rule_defs, ref)]
        metric_rules[binding_name] = compiled
        metric_rules[rule_name] = compiled
        desc = _rule_desc(rule_defs, ref)
        if desc:
            metric_rule_labels[binding_name] = desc
            metric_rule_labels[rule_name] = desc
    return metric_rules, metric_rule_labels


def _dictionary_entries(raw_dictionary) -> list[dict]:
    if not raw_dictionary:
        return []
    values = (
        raw_dictionary.get("values")
        if isinstance(raw_dictionary, dict) and "values" in raw_dictionary
        else raw_dictionary
    )
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    if isinstance(values, dict):
        entries = []
        for key, cfg in values.items():
            if not isinstance(cfg, dict):
                continue
            entry = dict(cfg)
            entry.setdefault("id", str(key))
            entry.setdefault("code", str(key))
            entries.append(entry)
        return entries
    return []


def _dictionary_allow_values(
    raw_dictionaries: dict, dictionary_cfg: dict
) -> list[str]:
    if not isinstance(dictionary_cfg, dict):
        return []
    dictionary_name = str(
        dictionary_cfg.get("dictionary") or dictionary_cfg.get("name") or "",
    ).strip()
    value_field = str(dictionary_cfg.get("value_field") or "").strip()
    if not dictionary_name or not value_field:
        return []
    raw_dictionary = (raw_dictionaries or {}).get(dictionary_name)
    values = []
    for entry in _dictionary_entries(raw_dictionary):
        value = entry.get(value_field)
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in values:
            values.append(text)
    return values


def _dictionary_identity(entry: dict, fields: tuple[str, ...]) -> str:
    for field_name in fields:
        value = str(entry.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _merge_dictionary_entries(
    raw_dictionary,
    incoming_entries: list[dict],
    *,
    identity_fields: tuple[str, ...],
):
    if not incoming_entries:
        return raw_dictionary

    merged = dict(raw_dictionary) if isinstance(raw_dictionary, dict) else {}
    values = [
        dict(entry)
        for entry in _dictionary_entries(raw_dictionary)
        if isinstance(entry, dict)
    ]
    index = {
        _dictionary_identity(entry, identity_fields): position
        for position, entry in enumerate(values)
        if _dictionary_identity(entry, identity_fields)
    }
    for entry in incoming_entries:
        item = dict(entry)
        identity = _dictionary_identity(item, identity_fields)
        if identity and identity in index:
            values[index[identity]].update(item)
        else:
            if identity:
                index[identity] = len(values)
            values.append(item)

    merged["values"] = values
    return merged


def _merge_naming_dictionaries(
    raw_dictionaries: dict,
    extra_dictionaries: dict | None = None,
) -> dict:
    merged = dict(raw_dictionaries or {})
    extra = extra_dictionaries or {}
    if extra.get("data_domains"):
        merged["data_domains"] = _merge_dictionary_entries(
            merged.get("data_domains"),
            _dictionary_entries(extra.get("data_domains")),
            identity_fields=("id", "code", "name"),
        )
    if extra.get("business_areas"):
        merged["business_areas"] = _merge_dictionary_entries(
            merged.get("business_areas"),
            _dictionary_entries(extra.get("business_areas")),
            identity_fields=("code", "id", "name"),
        )
    for name, dictionary in extra.items():
        if name in {"data_domains", "business_areas"}:
            continue
        merged.setdefault(name, dictionary)
    return merged


def _business_semantics_dictionaries_for_naming_path(path: Path) -> dict:
    catalog_path = path.parent / BUSINESS_SEMANTICS_FILE_NAME
    if not catalog_path.exists():
        return {}
    raw = (
        yaml.safe_load(catalog_path.read_text(encoding=core.TEXT_ENCODING))
        or {}
    )
    return business_semantics_dictionaries(
        raw if isinstance(raw, dict) else {}
    )


def load_naming_config(path=None, extra_dictionaries: dict | None = None):
    path = Path(path) if path else naming_config_path()
    with open(path, encoding=core.TEXT_ENCODING) as f:
        raw = yaml.safe_load(f) or {}
    if extra_dictionaries is None:
        extra_dictionaries = _business_semantics_dictionaries_for_naming_path(
            path
        )
    raw_dictionaries = _merge_naming_dictionaries(
        raw.get("dictionaries", {}) or {},
        extra_dictionaries,
    )
    types = {}
    for name, cfg in raw.get("types", {}).items():
        allow_cfg = cfg.get("allow", cfg.get("values"))
        dictionary_cfg = cfg.get("dictionary")
        if isinstance(allow_cfg, dict):
            dictionary_cfg = allow_cfg
            allow_values = _dictionary_allow_values(
                raw_dictionaries,
                dictionary_cfg,
            )
        elif dictionary_cfg:
            allow_values = _dictionary_allow_values(
                raw_dictionaries,
                dictionary_cfg,
            )
        else:
            allow_values = allow_cfg
        td = TypeDef(
            label=cfg.get("label", name),
            desc=cfg.get("desc", ""),
            allow=allow_values,
            patterns=_as_list(cfg.get("patterns", cfg.get("regex"))),
            dictionary=dictionary_cfg,
            values_from=cfg.get("values_from"),
        )
        types[name] = td

    rule_defs = raw.get("rules", {}) or {}
    bindings = raw.get("bindings", {}) or {}

    table_name_max_length = None
    if bindings.get("table"):
        layers, table_name_max_length = _compile_table_bindings(
            bindings.get("table") or {},
            rule_defs,
            types,
        )
        table_constraints = {}
    else:
        table_cfg = raw.get("table", {}) or {}
        table_constraints = {}
        table_templates_cfg = table_cfg
        if isinstance(table_cfg, dict):
            table_constraints = (
                table_cfg.get("constraints") or table_cfg.get("rules") or {}
            )
            if "templates" in table_cfg:
                table_templates_cfg = table_cfg.get("templates") or {}
            else:
                table_templates_cfg = {
                    name: cfg
                    for name, cfg in table_cfg.items()
                    if name not in ("constraints", "rules")
                }

        layers = {}
        for layer_name, template_defs in table_templates_cfg.items():
            if isinstance(template_defs, str) or (
                isinstance(template_defs, list)
                and template_defs
                and isinstance(template_defs[0], str)
            ):
                template_defs = [template_defs]

            templates = []
            for template in template_defs:
                templates.extend(_parse_template_variants(template, types))

            layers[layer_name] = LayerDef(
                templates=templates,
                constraints=[table_constraints] * len(templates),
                template_rules=[
                    {
                        "name": layer_name,
                        "description": "",
                        "raw_expr": template,
                        "constraints": table_constraints,
                    }
                    for template in _as_list(template_defs)
                    for _ in _parse_template_variants(template, types)
                ],
            )

    if bindings.get("column"):
        (
            column_segments,
            column_templates,
            column_template_rules,
            common_columns,
        ) = _compile_column_bindings(
            bindings.get("column") or {},
            rule_defs,
            types,
        )
    else:
        col_cfg = raw.get("columns", {}) or {}
        raw_col_seg = col_cfg.get("segments") or col_cfg.get("pattern", "")
        column_templates = (
            _parse_template_variants(raw_col_seg, types) if raw_col_seg else []
        )
        column_segments = column_templates[0] if column_templates else []
        column_template_rules = [
            {
                "name": "COLUMN",
                "description": "",
                "raw_expr": raw_col_seg,
                "constraints": {},
            }
            for _ in column_templates
        ]
        common_columns = set(col_cfg.get("common_columns", []))

    metric_rules = {}
    metric_rule_labels = {}
    if bindings.get("metric"):
        bound_metric_rules, bound_metric_labels = _compile_metric_bindings(
            bindings.get("metric") or {},
            rule_defs,
        )
        metric_rules.update(bound_metric_rules)
        metric_rule_labels.update(bound_metric_labels)
    metric_cfg = raw.get("metrics", {}) or {}
    for rule_name, rule_cfg in metric_cfg.items():
        metric_rules[rule_name] = _parse_metric_rule_defs(rule_cfg, types)
        if isinstance(rule_cfg, dict) and rule_cfg.get("desc"):
            metric_rule_labels[rule_name] = str(rule_cfg["desc"])

    table_name_cfg = raw.get("table_name", {})
    if table_name_max_length is None:
        table_name_max_length = (
            table_constraints.get("max_length")
            if isinstance(table_constraints, dict)
            else None
        )
    if table_name_max_length is None:
        table_name_max_length = (
            table_name_cfg.get("max_length")
            if isinstance(table_name_cfg, dict)
            else None
        )

    table_name_max_length = (
        int(table_name_max_length)
        if table_name_max_length is not None
        else None
    )

    return NamingConfig(
        types=types,
        layers=layers,
        column_segments=column_segments,
        common_columns=common_columns,
        column_templates=column_templates,
        column_template_rules=column_template_rules,
        table_name_max_length=table_name_max_length,
        metric_rules=metric_rules,
        metric_rule_labels=metric_rule_labels,
        dictionaries=raw_dictionaries,
        business_domain_config=business_domain_config_from_dictionaries(
            raw_dictionaries
        ),
    )


def get_naming_config(project: str = None) -> NamingConfig:
    if project and project in core.PROJECT_CONFIG:
        cfg_file = core.PROJECT_CONFIG[project].get(
            "naming_config", "naming_config.yaml"
        )
        key = f"{project}:{cfg_file}"
    else:
        cfg_file = "naming_config.yaml"
        key = "__default__"

    if key not in _naming_config_cache:
        extra_dictionaries = None
        if project and project in core.PROJECT_CONFIG:
            extra_dictionaries = business_semantics_dictionaries(
                load_business_semantics_catalog(project)
            )
        _naming_config_cache[key] = load_naming_config(
            core.PROJECT_ROOT / cfg_file,
            extra_dictionaries=extra_dictionaries,
        )
    return _naming_config_cache[key]
