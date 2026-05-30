"""
全局配置文件
"""
import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent

# ============================================================
# 命名规范配置
# ============================================================

NAMING_CONFIG_PATH = PROJECT_ROOT / "naming_config.yaml"


@dataclass
class TypeDef:
    label: str
    desc: str = ""
    regex: Optional[str] = None
    values: Optional[list[str]] = None
    _compiled: Optional[re.Pattern] = None

    def validate(self, value: str) -> bool:
        if self.values is not None:
            return value in self.values
        if self._compiled is not None:
            return bool(self._compiled.match(value))
        return True


@dataclass
class LayerDef:
    rank: int
    templates: list


@dataclass
class NamingConfig:
    types: dict[str, TypeDef]
    layers: dict[str, LayerDef]
    layer_order: list[str]
    column_segments: list
    common_columns: set[str]

    def determine_layer(self, table_name: str) -> str:
        short = table_name.split(".")[-1]
        for name in self.layer_order:
            if name in self.layers:
                for segs in self.layers[name].templates:
                    if self._match_segments(short, segs) is not None:
                        return name
        return "OTHER"

    def layer_rank(self, layer_name: str) -> int:
        layer = self.layers.get(layer_name)
        return layer.rank if layer else -1

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
        skip_right = 0  # 从右侧跳过已匹配的段

        # Phase 1: match literals and fixed-value types from left
        while left <= right:
            seg = segments[left]
            if seg["kind"] != "literal" and seg.get("sep_before"):
                # 有 leading separator → 不是从开头开始的段，暂停
                if seg["kind"] == "type":
                    td = self.types.get(seg["name"])
                    if td and td.values is not None:
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
            rest = remaining[len(sep_before):]

            if seg["kind"] == "literal":
                if not rest.startswith(sname):
                    if seg.get("optional", False):
                        left += 1
                        continue
                    return None
                remaining = rest[len(sname):]
                if sep_after:
                    if not remaining.startswith(sep_after):
                        if seg.get("optional", False):
                            left += 1
                            continue
                        return None
                    remaining = remaining[len(sep_after):]
                left += 1

            elif seg["kind"] == "type":
                td = self.types.get(sname)
                if td and td.values is not None:
                    matched = None
                    for v in sorted(td.values, key=len, reverse=True):
                        core = str(v)
                        if rest.startswith(core):
                            after = rest[len(core):]
                            if sep_after:
                                if not after.startswith(sep_after):
                                    continue
                                after = after[len(sep_after):]
                            matched = v
                            remaining = after
                            break
                    if matched is not None:
                        result[sname] = matched
                        left += 1
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
            has_values = td and td.values is not None

            if not has_values:
                break  # 只有 values type 能从右侧匹配

            sep_before = seg.get("sep_before", "")
            if seg.get("concat_left"):
                check_prefix = ""
            else:
                check_prefix = sep_before or "_"
            matched = None
            for v in sorted(td.values, key=len, reverse=True):
                suffix = check_prefix + str(v)
                if remaining.endswith(suffix):
                    # 如果是独立 _，前一段应该是 _ 字面量，一并跳过
                    if not sep_before and not seg.get("concat_left") and right > left:
                        prev = segments[right - 1]
                        if prev["kind"] == "literal" and prev["name"] == "_":
                            right -= 1  # skip the _ literal
                    matched = v
                    remaining = remaining[:-len(suffix)]
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
            rest = remaining[len(sep_before):]

            if seg["kind"] == "literal":
                if not rest.startswith(sname):
                    if optional:
                        left += 1
                        continue
                    return None
                remaining = rest[len(sname):]
                left += 1

            elif seg["kind"] == "type":
                td = self.types.get(sname)
                if td and td.values is not None:
                    matched = None
                    for v in sorted(td.values, key=len, reverse=True):
                        if rest.startswith(v):
                            matched = v
                            remaining = rest[len(v):]
                            break
                    if matched is not None:
                        _assign(result, sname, matched)
                        left += 1
                    elif optional:
                        left += 1
                    else:
                        return None
                elif td and td.regex is not None:
                    # 判断 regex 是否允许下划线
                    allows_underscore = "_" in (td.regex or "")
                    if allows_underscore:
                        # 变长 type：消耗到下一个段之前
                        if left + 1 <= right and not optional:
                            # 后面还有段，找下一个段需要的前缀
                            next_seg = segments[left + 1]
                            next_prefix = next_seg.get("sep_before", "") or next_seg["name"]
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
                            _assign(result, sname, rest)
                            remaining = ""
                            left += 1
                        else:
                            _assign(result, sname, rest)
                            remaining = ""
                            left += 1
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


def _parse_segments(raw: list, types: dict) -> list:
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
        raw_str = str(item)
        optional = False
        is_type = False
        concat_left = False

        if raw_str.startswith("$"):
            is_type = True
            raw_str = raw_str[1:]
            if raw_str.startswith("+"):
                concat_left = True
                raw_str = raw_str[1:]

        if raw_str.endswith("?"):
            optional = True
            raw_str = raw_str[:-1]

        if is_type:
            parsed.append({"name": raw_str, "kind": "type", "optional": optional,
                           "sep_before": "", "sep_after": "", "concat_left": concat_left})
        else:
            parsed.append({"name": raw_str, "kind": "literal", "optional": optional,
                           "sep_before": "", "sep_after": "", "concat_left": concat_left})

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
            literal = {"name": "_", "kind": "literal", "optional": False,
                       "sep_before": "", "sep_after": "", "concat_left": False}
            parsed.insert(i + 1, literal)
            i += 1
        i += 1
    return parsed


def _parse_template(template, types: dict) -> list:
    """支持列表或字符串格式。"""
    if isinstance(template, list):
        return _parse_segments(template, types)
    # 字符串格式 "ods_{source}_{entity}_{load_type}" → 添加 $ 前缀
    raw = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.find("}", i)
            content = template[i + 1:j]
            raw.append("$" + content)  # {type} → $type
            i = j + 1
        else:
            j = template.find("{", i)
            if j == -1:
                raw.append(template[i:])
                break
            if j > i:
                raw.append(template[i:j])
            i = j
    return _parse_segments(raw, types)


def load_naming_config(path=None):
    path = Path(path) if path else NAMING_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    types = {}
    for name, cfg in raw.get("types", {}).items():
        td = TypeDef(
            label=cfg.get("label", name),
            desc=cfg.get("desc", ""),
            regex=cfg.get("regex"),
            values=cfg.get("values"),
        )
        if td.regex:
            td._compiled = re.compile(td.regex)
        types[name] = td
    rank_map = {}
    layer_order = []
    layer_cfg = raw.get("layers", [])
    if layer_cfg:
        for r, item in enumerate(layer_cfg):
            if isinstance(item, list):
                for name in item:
                    rank_map[name] = r
                    if name not in layer_order:
                        layer_order.append(name)
            else:
                rank_map[item] = r
                if item not in layer_order:
                    layer_order.append(item)
    else:
        for r, name in enumerate(raw.get("table", {}).keys()):
            rank_map[name] = r
            if name not in layer_order:
                layer_order.append(name)

    layers = {}
    for layer_name, template_defs in raw.get("table", {}).items():
        if isinstance(template_defs[0], str):
            template_defs = [template_defs]
        
        templates = []
        for template in template_defs:
            parsed = _parse_template(template, types)
            templates.append(parsed)

        rank = rank_map.get(layer_name, -1)
        layers[layer_name] = LayerDef(rank=rank, templates=templates)
        if layer_name not in layer_order:
            layer_order.append(layer_name)

    col_cfg = raw.get("columns", {})
    raw_col_seg = col_cfg.get("segments") or col_cfg.get("pattern", "")
    column_segments = _parse_template(raw_col_seg, types) if raw_col_seg else []
    common_columns = set(col_cfg.get("common_columns", []))
    
    return NamingConfig(
        types=types,
        layers=layers,
        layer_order=layer_order,
        column_segments=column_segments,
        common_columns=common_columns,
    )


_naming_config_cache = {}


def get_naming_config(project: str = None, config_file: str = None) -> NamingConfig:
    global _naming_config_cache
    if config_file:
        cfg_file = config_file
        key = cfg_file
    elif project and project in PROJECT_CONFIG:
        cfg_file = PROJECT_CONFIG[project].get("naming_config", "naming_config.yaml")
        key = cfg_file
    else:
        cfg_file = "naming_config.yaml"
        key = "__default__"

    if key not in _naming_config_cache:
        _naming_config_cache[key] = load_naming_config(PROJECT_ROOT / cfg_file)
    return _naming_config_cache[key]



# 项目配置映射
# 每个数据集市项目拥有两个库:
#   db     - 生产库 (ETL 读写, verify 时作为源)
#   qa_db  - 验证库 (verify 时写入, 用于重构对比)
PROJECT_CONFIG = {
    "shop": {
        "dir": "shop",
        "db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "lineage_db": "shop_lineage",
        "naming_config": "naming_config_enterprise.yaml"
    },
    "finance_analytics": {
        "dir": "finance_analytics",
        "db": "finance_analytics_dm",
        "qa_db": "finance_analytics_dm_qa",
        "lineage_db": "finance_analytics_lineage",
    },
}

# 兼容旧的命名
PROJECT_MAP = PROJECT_CONFIG

# 数据库环境配置 (MySQL 协议)
# 环境 = 物理集群, 不同的 host/port 组合
# qa_user = 操作验证库 (qa_db) 的专用用户, 权限仅限 qa_db
DB_ENV_CONFIG = {
    "prod": {"host": "172.16.0.90", "port": 19030, "user": "root", "qa_user": "qa"},
    "test": {"host": "172.16.0.90", "port": 9034, "user": "root", "qa_user": "qa"},
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
