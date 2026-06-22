"""
全局配置文件
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent
TEXT_ENCODING = "utf-8"

# 项目层级顺序。表的实际层级来自 models/{table}.yaml，这里只定义跨层依赖
# 和展示排序时需要的稳定顺序。
LAYER_ORDER = [
    ["ODS"],
    ["DIM", "DWD"],
    ["DWS"],
    ["ADS"],
]

# ============================================================
# 命名规范配置
# ============================================================

NAMING_CONFIG_PATH = PROJECT_ROOT / "naming_config.yaml"


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
        parts = []
        for segment in segments:
            name = segment.get("name", "")
            token = (
                f"{{{name}}}" if segment.get("kind") == "type" else str(name)
            )
            if segment.get("optional"):
                token += "?"
            if segment.get("concat_left") and parts:
                parts[-1] = parts[-1] + token
            else:
                parts.append(token)
        return " ".join(parts)

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

    def diagnose_table_name(self, name: str, layer: str) -> dict:
        layer_def = self.layers.get(layer)
        attempts = []
        if layer_def:
            rules = layer_def.template_rules or [
                {} for _ in layer_def.templates
            ]
            for segments, rule in zip(layer_def.templates, rules):
                attempts.append(self.diagnose_segments(name, segments, rule))

        return {
            "actual": name,
            "layer": layer,
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


@dataclass
class DomainDef:
    id: str
    code: str
    name: str
    desc: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class BusinessAreaDef:
    id: str
    code: str
    name: str
    desc: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class BusinessDomainConfig:
    domains: dict[str, DomainDef]
    business_areas: dict[str, BusinessAreaDef]

    @property
    def domain_ids(self) -> list[str]:
        return sorted(self.domains)

    @property
    def business_area_codes(self) -> list[str]:
        return sorted(self.business_areas)

    def is_valid_domain(self, value: str) -> bool:
        return str(value or "").strip() in self.domains

    def is_valid_business_area(self, value: str) -> bool:
        return str(value or "").strip().upper() in self.business_areas

    def normalize_business_area(self, value: str) -> str:
        return str(value or "").strip().upper()

    def normalize_domain(self, value: str) -> str:
        raw = str(value or "").strip()
        if raw in self.domains:
            return raw
        if raw.isdigit():
            padded = raw.zfill(2)
            if padded in self.domains:
                return padded
        upper = raw.upper()
        for domain in self.domains.values():
            if upper == domain.code:
                return domain.id
        return raw

    def prompt_options(self) -> dict:
        return {
            "domains": [
                {
                    "id": domain.id,
                    "code": domain.code,
                    "name": domain.name,
                    "description": domain.desc,
                }
                for domain in self.domains.values()
            ],
            "business_areas": [
                {
                    "id": area.id,
                    "code": area.code,
                    "name": area.name,
                    "description": area.desc,
                }
                for area in self.business_areas.values()
            ],
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


def _business_semantics_dictionaries(catalog: dict) -> dict:
    if not isinstance(catalog, dict) or not catalog:
        return {}
    dictionaries = {}
    data_domains = [
        dict(entry)
        for entry in _dictionary_entries(catalog.get("data_domains"))
    ]
    business_areas = [
        dict(entry)
        for entry in _dictionary_entries(catalog.get("business_areas"))
    ]
    if data_domains:
        dictionaries["data_domains"] = {"values": data_domains}
    if business_areas:
        dictionaries["business_areas"] = {"values": business_areas}
    return dictionaries


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
    raw = yaml.safe_load(catalog_path.read_text(encoding=TEXT_ENCODING)) or {}
    return _business_semantics_dictionaries(
        raw if isinstance(raw, dict) else {}
    )


def load_naming_config(path=None, extra_dictionaries: dict | None = None):
    path = Path(path) if path else NAMING_CONFIG_PATH
    with open(path, encoding=TEXT_ENCODING) as f:
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
        business_domain_config=_business_domain_config_from_dictionaries(
            raw_dictionaries
        ),
    )


BUSINESS_SEMANTICS_FILE_NAME = "business_semantics.yaml"

_naming_config_cache = {}
_model_metadata_cache = {}
_business_semantics_cache = {}


def _as_keywords(value) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _load_domain_defs(raw_domains) -> dict[str, DomainDef]:
    domains = {}
    for cfg in _dictionary_entries(raw_domains):
        domain_id = str(cfg.get("id") or "").strip()
        if not domain_id:
            continue
        domain_code = str(cfg.get("code") or domain_id).strip().upper()
        domains[domain_id] = DomainDef(
            id=domain_id,
            code=domain_code,
            name=str(cfg.get("name") or domain_code),
            desc=str(cfg.get("desc") or cfg.get("description") or ""),
            keywords=_as_keywords(cfg.get("keywords")),
        )
    return domains


def _load_business_area_defs(raw_areas) -> dict[str, BusinessAreaDef]:
    business_areas = {}
    for cfg in _dictionary_entries(raw_areas):
        area_code = str(cfg.get("code") or "").strip().upper()
        if not area_code:
            continue
        business_areas[area_code] = BusinessAreaDef(
            id=str(cfg.get("id") or area_code),
            code=area_code,
            name=str(cfg.get("name") or area_code),
            desc=str(cfg.get("desc") or cfg.get("description") or ""),
            keywords=_as_keywords(cfg.get("keywords")),
        )
    return business_areas


def _business_domain_config_from_dictionaries(
    raw_dictionaries: dict,
) -> Optional[BusinessDomainConfig]:
    raw_domains = (raw_dictionaries or {}).get("data_domains")
    raw_areas = (raw_dictionaries or {}).get("business_areas")
    if not raw_domains or not raw_areas:
        return None
    domains = _load_domain_defs(raw_domains)
    business_areas = _load_business_area_defs(raw_areas)
    if not domains or not business_areas:
        return None
    return BusinessDomainConfig(
        domains=domains,
        business_areas=business_areas,
    )


def business_semantics_path(project: str) -> Optional[Path]:
    cfg = PROJECT_CONFIG.get(project)
    if not cfg:
        return None
    return PROJECT_ROOT / cfg["dir"] / BUSINESS_SEMANTICS_FILE_NAME


def load_business_semantics_catalog(project: str) -> dict:
    path = business_semantics_path(project)
    if not path:
        return {}
    cache_key = f"{project}:{path}"
    if cache_key in _business_semantics_cache:
        return _business_semantics_cache[cache_key]
    if not path.exists():
        _business_semantics_cache[cache_key] = {}
        return {}
    raw = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING)) or {}
    if not isinstance(raw, dict):
        raw = {}
    _business_semantics_cache[cache_key] = raw
    return raw


def _business_domain_config_from_semantics_catalog(
    catalog: dict,
) -> Optional[BusinessDomainConfig]:
    if not catalog:
        return None
    domains = _load_domain_defs(catalog.get("data_domains"))
    business_areas = _load_business_area_defs(catalog.get("business_areas"))
    if not domains or not business_areas:
        return None
    return BusinessDomainConfig(
        domains=domains,
        business_areas=business_areas,
    )


def get_business_domain_config(
    project: str = None,
) -> Optional[BusinessDomainConfig]:
    if project:
        catalog_config = _business_domain_config_from_semantics_catalog(
            load_business_semantics_catalog(project)
        )
        if catalog_config:
            return catalog_config
    return get_naming_config(project).business_domain_config


def project_dir(project: str) -> Optional[Path]:
    """返回项目根目录."""
    cfg = PROJECT_CONFIG.get(project)
    if not cfg:
        return None
    return PROJECT_ROOT / cfg["dir"]


def project_artifact_dir(project: str, *parts: str) -> Optional[Path]:
    """返回项目级生成产物目录."""
    base_dir = project_dir(project)
    if not base_dir:
        return None
    return base_dir.joinpath(*parts)


def lineage_data_path(project: str, snapshot_id: str | None = None) -> Path:
    """返回项目血缘 JSON 默认路径."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    if snapshot_id:
        return lineage_dir / f"lineage_data_{snapshot_id}.json"
    return lineage_dir / "lineage_data.json"


def job_dag_path(project: str) -> Path:
    """返回项目作业 DAG 默认路径."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "job_dag.json"


def lineage_task_cache_path(project: str) -> Path:
    """返回项目 task 级血缘缓存默认路径."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "task_lineage_cache.json"


def lineage_html_path(project: str) -> Path:
    """返回项目字段血缘 HTML 默认路径."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "lineage.html"


def lineage_job_html_path(project: str) -> Path:
    """返回项目作业血缘 HTML 默认路径."""
    lineage_dir = project_artifact_dir(project, "lineage")
    if lineage_dir is None:
        raise KeyError(f"未知项目: {project}")
    return lineage_dir / "lineage_job.html"


def assess_result_path(project: str) -> Path:
    """返回项目中间层评估结果默认路径."""
    assess_dir = project_artifact_dir(project, "assess")
    if assess_dir is None:
        raise KeyError(f"未知项目: {project}")
    return assess_dir / "assess_result.json"


def model_metadata_result_path(project: str) -> Path:
    """返回项目模型元数据回写结果默认路径."""
    assess_dir = project_artifact_dir(project, "assess")
    if assess_dir is None:
        raise KeyError(f"未知项目: {project}")
    return assess_dir / "model_metadata_result.json"


def assess_cache_path(project: str, filename: str) -> Path:
    """返回项目评估缓存文件默认路径."""
    cache_dir = project_artifact_dir(project, "assess", "cache")
    if cache_dir is None:
        raise KeyError(f"未知项目: {project}")
    return cache_dir / filename


def project_ods_asset_dir(project: str, asset_kind: str) -> Optional[Path]:
    """返回 ODS 资产按 catalog/database 组织后的目录."""
    cfg = PROJECT_CONFIG.get(project)
    base_dir = project_dir(project)
    if not cfg or not base_dir:
        return None
    catalog = str(cfg.get("catalog") or "internal")
    database = str(cfg.get("db") or "")
    return base_dir / "ods" / asset_kind / catalog / database


def _configured_databases(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]
    return [str(item) for item in raw_values if str(item)]


def project_ods_source_catalogs(project: str) -> dict[str, dict]:
    """返回 ODS 源 catalog 配置，默认项目 ODS catalog 使用 Doris DDL."""
    cfg = PROJECT_CONFIG.get(project)
    if not cfg:
        return {}

    default_catalog = str(cfg.get("catalog") or "internal")
    default_db = str(cfg.get("db") or "")
    result = {
        default_catalog: {
            "ddl_dialect": "doris",
            "databases": [default_db] if default_db else [],
        }
    }

    raw_catalogs = cfg.get("ods_source_catalogs") or {}
    if not isinstance(raw_catalogs, dict):
        return result

    for raw_catalog, raw_catalog_cfg in raw_catalogs.items():
        catalog = str(raw_catalog)
        if not catalog:
            continue
        if isinstance(raw_catalog_cfg, str):
            catalog_cfg = {"ddl_dialect": raw_catalog_cfg}
        elif isinstance(raw_catalog_cfg, dict):
            catalog_cfg = dict(raw_catalog_cfg)
        else:
            catalog_cfg = {}
        existing = result.setdefault(catalog, {})
        existing.update(catalog_cfg)
        existing.setdefault("ddl_dialect", "doris")
        if "databases" not in existing and "database" in existing:
            existing["databases"] = _configured_databases(
                existing.get("database")
            )

    return result


def ods_source_catalog_ddl_dialect(project: str, catalog: str) -> str:
    """返回指定 ODS source catalog 的 DDL 方言，默认 Doris."""
    catalog_key = str(catalog or "")
    catalog_cfg = project_ods_source_catalogs(project).get(catalog_key) or {}
    return str(catalog_cfg.get("ddl_dialect") or "doris")


def project_ods_asset_dirs(project: str, asset_kind: str) -> list[Path]:
    """返回配置化 ODS 资产目录，按 catalog/database 组织."""
    base_dir = project_dir(project)
    if not base_dir:
        return []

    ods_root = base_dir / "ods" / asset_kind
    dirs = []
    seen = set()
    for catalog, catalog_cfg in project_ods_source_catalogs(project).items():
        catalog_dir = ods_root / catalog
        databases = _configured_databases(catalog_cfg.get("databases"))
        if not databases and catalog_dir.exists():
            databases = [
                path.name
                for path in sorted(catalog_dir.iterdir())
                if path.is_dir()
            ]
        for database in databases:
            asset_dir = catalog_dir / database
            if asset_dir in seen:
                continue
            seen.add(asset_dir)
            dirs.append(asset_dir)
    return dirs


def project_asset_dirs(project: str, asset_kind: str) -> list[Path]:
    """返回项目资产目录，包含通用目录和 ODS 专用目录."""
    base_dir = project_dir(project)
    if not base_dir:
        return []
    dirs = [base_dir / asset_kind]
    for ods_dir in project_ods_asset_dirs(project, asset_kind):
        dirs.append(ods_dir)
    return dirs


def iter_project_asset_files(
    project: str,
    asset_kind: str,
    pattern: str,
) -> list[Path]:
    """按稳定顺序返回项目资产文件."""
    files: list[Path] = []
    seen: set[Path] = set()
    for asset_dir in project_asset_dirs(project, asset_kind):
        if not asset_dir.exists():
            continue
        for asset_path in sorted(asset_dir.glob(pattern)):
            if asset_path in seen:
                continue
            seen.add(asset_path)
            files.append(asset_path)
    return files


def model_path_for_table(
    project: str,
    table_name: str,
    *,
    layer: str | None = None,
) -> Path:
    """返回表级模型元数据写入路径."""
    cfg = PROJECT_CONFIG[project]
    filename = f"{table_name}.yaml"
    normalized_layer = str(layer or "").upper()
    if normalized_layer == "ODS":
        ods_dir = project_ods_asset_dir(project, "models")
        if ods_dir:
            return ods_dir / filename

    existing_ods_dir = project_ods_asset_dir(project, "models")
    if existing_ods_dir and (existing_ods_dir / filename).exists():
        return existing_ods_dir / filename

    return PROJECT_ROOT / cfg["dir"] / "models" / filename


def load_model_metadata(project: str) -> dict:
    """加载项目 models/{table}.yaml 表级元数据."""
    if project in _model_metadata_cache:
        return _model_metadata_cache[project]

    cfg = PROJECT_CONFIG.get(project)
    if not cfg:
        _model_metadata_cache[project] = {}
        return {}

    model_paths = iter_project_asset_files(project, "models", "*.yaml")
    if not model_paths:
        _model_metadata_cache[project] = {}
        return {}

    metadata = {}
    for model_path in model_paths:
        raw = (
            yaml.safe_load(model_path.read_text(encoding=TEXT_ENCODING)) or {}
        )
        if not isinstance(raw, dict):
            continue
        name = raw.get("name") or model_path.stem
        raw = dict(raw)
        raw["name"] = name
        metadata[name] = raw

    _model_metadata_cache[project] = metadata
    return metadata


def get_model_metadata(table_name: str, project: str) -> Optional[dict]:
    short = table_name.split(".")[-1]
    return load_model_metadata(project).get(short)


def get_model_layer(table_name: str, project: str) -> Optional[str]:
    metadata = get_model_metadata(table_name, project)
    if not metadata:
        return None
    layer = metadata.get("layer")
    return str(layer).upper() if layer else None


def get_model_names_by_layer(project: str, layer: str) -> list[str]:
    """按 models 元数据返回指定层级的表名."""
    target_layer = str(layer).upper()
    names = []
    for name, metadata in load_model_metadata(project).items():
        model_layer = metadata.get("layer")
        if model_layer and str(model_layer).upper() == target_layer:
            names.append(name)
    return sorted(names)


def determine_layer(table_name: str, project: str = None) -> str:
    """从项目 models 显式元数据获取表层级."""
    short = table_name.split(".")[-1]
    if not project:
        return "OTHER"
    return get_model_layer(short, project) or "OTHER"


def layer_rank(layer_name: str) -> int:
    """返回稳定的项目层级顺序，未知层级返回 -1."""
    normalized = str(layer_name or "").upper()
    for rank, group in enumerate(LAYER_ORDER):
        if normalized in group:
            return rank
    return -1


def get_naming_config(project: str = None) -> NamingConfig:
    global _naming_config_cache
    if project and project in PROJECT_CONFIG:
        cfg_file = PROJECT_CONFIG[project].get(
            "naming_config", "naming_config.yaml"
        )
        key = f"{project}:{cfg_file}"
    else:
        cfg_file = "naming_config.yaml"
        key = "__default__"

    if key not in _naming_config_cache:
        extra_dictionaries = None
        if project and project in PROJECT_CONFIG:
            extra_dictionaries = _business_semantics_dictionaries(
                load_business_semantics_catalog(project)
            )
        _naming_config_cache[key] = load_naming_config(
            PROJECT_ROOT / cfg_file,
            extra_dictionaries=extra_dictionaries,
        )
    return _naming_config_cache[key]


# 项目配置映射
# 每个数据集市项目拥有一个默认 catalog 和两个库:
#   catalog - 默认 catalog, 未显式声明时使用 internal
#   db      - 生产库 (ETL 读写, verify 时作为源)
#   qa_db   - 验证库 (verify 时写入, 用于重构对比)
#   ods_source_catalogs - 可选，ODS 源 catalog 配置，如 {"hive": {"ddl_dialect": "hive"}}
PROJECT_CONFIG = {
    "shop": {
        "dir": "shop",
        "catalog": "internal",
        "db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "lineage_db": "shop_lineage",
        "naming_config": "shop/naming_config.yaml",
    },
    "finance_analytics": {
        "dir": "finance_analytics",
        "catalog": "internal",
        "db": "finance_analytics_dm",
        "qa_db": "finance_analytics_dm_qa",
        "lineage_db": "finance_analytics_lineage",
        "naming_config": "finance_analytics/naming_config.yaml",
    },
}

# 兼容旧的命名
PROJECT_MAP = PROJECT_CONFIG

# 数据库环境配置 (MySQL 协议)
# 环境 = 物理集群, 不同的 host/port 组合
# qa_user = 操作验证库 (qa_db) 的专用用户, 权限仅限 qa_db
DB_ENV_CONFIG = {
    "prod": {
        "host": "172.16.0.90",
        "port": 19030,
        "user": "root",
        "qa_user": "qa",
    },
    "test": {
        "host": "172.16.0.90",
        "port": 9034,
        "user": "root",
        "qa_user": "qa",
    },
}

# Doris HTTP 协议配置 (Stream Load 使用)
DORIS_HTTP_PORT = 8030

# 默认提供 prod 环境的快捷访问
DORIS_HOST = DB_ENV_CONFIG["prod"]["host"]
DORIS_PORT = DB_ENV_CONFIG["prod"]["port"]
DORIS_USER = DB_ENV_CONFIG["prod"]["user"]
DORIS_QA_USER = DB_ENV_CONFIG["prod"]["qa_user"]


def get_mysql_cmd(env: str = "prod", qa: bool = False) -> list[str]:
    """获取 mysql 命令行参数数组.

    Args:
        env: 物理环境 (prod / test)
        qa: True 时使用 qa_user 连接, 用于操作验证库
    """
    cfg = DB_ENV_CONFIG[env]
    user = cfg["qa_user"] if qa else cfg["user"]
    return ["mysql", f"-h{cfg['host']}", f"-P{cfg['port']}", f"-u{user}"]
