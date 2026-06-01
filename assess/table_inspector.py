import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from assess.context_builder import TableContext


PROMPT_VERSION = "table-inspector-v3"
VALID_LAYERS = {"ODS", "DWD", "DWS", "ADS", "DIM", "OTHER"}
VALID_TABLE_TYPES = {"dimension", "fact", "other"}
COLUMN_GROUPS = ("atomic_metrics", "derived_metrics", "dimensions", "others")
VALIDATION_ERROR_KEYS = ("unknown_columns", "duplicate_columns")
VALIDATION_WARNING_KEYS = ("missing_columns",)


def _empty_columns() -> dict[str, list[dict[str, Any]]]:
    return {group: [] for group in COLUMN_GROUPS}


@dataclass
class TableInspectResult:
    table_name: str
    declared_layer: str
    inferred_layer: str  # "ODS" | "DWD" | "DWS" | "ADS" | "DIM" | "OTHER"
    table_type: str      # "dimension" | "fact" | "other"
    confidence: float
    reasoning_steps: list[str]
    columns: dict[str, list[dict[str, Any]]] = field(
        default_factory=_empty_columns)
    validation: dict[str, list[str]] = field(default_factory=dict)
    retry_count: int = 0

    @property
    def is_violating_declared_layer(self) -> bool:
        """系统根据声明层级和推断层级计算，不由 LLM 返回。"""
        declared = str(self.declared_layer or "").upper()
        inferred = str(self.inferred_layer or "").upper()
        if self.confidence <= 0 or not declared or not inferred:
            return False
        return declared != inferred

    @property
    def is_fact_table(self) -> bool:
        return self.table_type == "fact"

    @property
    def atomic_metrics(self) -> list[dict[str, Any]]:
        return self.columns.get("atomic_metrics", [])

    @property
    def derived_metrics(self) -> list[dict[str, Any]]:
        return self.columns.get("derived_metrics", [])

    @property
    def dimensions(self) -> list[dict[str, Any]]:
        return self.columns.get("dimensions", [])

    @property
    def others(self) -> list[dict[str, Any]]:
        return self.columns.get("others", [])

    @property
    def status(self) -> str:
        """返回 passed/warning/blocked，供回写流程做安全决策。"""
        if self.confidence <= 0:
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_ERROR_KEYS):
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_WARNING_KEYS):
            return "warning"
        return "passed"


def build_prompt(ctx: TableContext) -> str:
    prompt = f"""你是一位资深数据仓库架构师和指标治理专家。你的任务是根据给定的表结构、ETL 加工逻辑和血缘关系，完成一次统一巡检:
1. 客观推断这张表真实应该归属的数仓分层。
2. 判断它的物理表类型（维度表/事实表/其他）。
3. 如果原始配置层级是 DWD 且你判断它是事实表，则对字段分组识别原子指标、派生指标、维度字段和其他字段。

## 数仓分层判定标准
- ODS (贴源层): 直接同步业务库，通常不含复杂的转化逻辑，数据粒度与源库完全一致。
- DWD (明细宽表层): 对 ODS 进行数据清洗、维度退化(多表 JOIN 拉宽)，但**保持事务明细粒度，严禁包含聚合(GROUP BY)操作**。
- DWS (汇总层): 包含明确的聚合操作(GROUP BY/SUM/COUNT)，用于计算公共维度下的周期性指标，具备**被多个下游复用**的特征。
- ADS (应用层): 面向最终报表或业务大屏的定制化数据，可能包含复杂的衍生指标，最明显的特征是**下游通常不再被其他数据表引用 (出度为 0)**。
- DIM (公共维度表): 记录实体属性，主键通常为单一实体 ID，被其他宽表广泛 LEFT JOIN。

## 表类型判定标准
- dimension: 维度表。描述业务实体属性(如客户、商品、门店), 缓慢变化, 常常作为维表被 JOIN。
- fact: 事实表。记录业务事件/交易，包含可聚合度量字段，通常有时间分区。
- other: 其他类型。

## DWD 事实表字段分组标准
- atomic_metrics: 基于某一业务过程下不可再拆分的基础度量，通常是金额、数量、余额、单价、次数等可度量字段，不包含聚合、比率、分数或多字段计算。尽量填写 business_process/action/measure。
- derived_metrics: 只放度量型派生指标，即由其他度量字段计算、聚合、比率、窗口函数、评分等生成的数值指标。尽量填写 expression/derived_from。
- dimensions: 主键、外键、日期、时间、状态、标签、枚举、布尔标志、退化维度、实体属性等分析维度字段。即使它们由 DATE_FORMAT、CASE WHEN 或其他表达式生成，只要用于切片/过滤/分组而不是作为度量，也应放入 dimensions。
- others: 审计字段、技术字段、无法判断字段。
- DWD 事实表只能包含 atomic_metrics；derived_metrics 属于 DWD 违规风险。

## 表级特征信息
- 原始表名: {ctx.table_name}
- 原始配置层级: {ctx.layer}
- 下游被引用次数: {len(ctx.downstream_tables)}
- 距 ODS 最小跳数: {ctx.depth_from_ods}

## DDL
{ctx.ddl}

"""
    if ctx.etl_sql:
        prompt += f"## ETL 加工逻辑\n{ctx.etl_sql}\n\n"

    prompt += f"""## 血缘关系
上游表: {', '.join(ctx.upstream_tables) if ctx.upstream_tables else '无'}
下游表: {', '.join(ctx.downstream_tables) if ctx.downstream_tables else '无'}

## 思考步骤
1. 首先分析 ETL_SQL 中是否包含 GROUP BY 等聚合操作，如果有，排除 DWD 和 ODS。
2. 观察下游被引用次数。如果为 0，大概率是 ADS；如果 > 1，倾向于 DWS 或 DWD。
3. 判断是否为 dimension（主键是否为实体属性）。
4. 如果原始配置层级是 DWD 且表类型为 fact，再按字段语义、DDL 注释、ETL 表达式和业务过程分组。

请严格返回 JSON 格式数据，不要返回 Markdown，不要返回额外解释。不要返回 is_violating_declared_layer，这个字段由系统计算。
如果不需要做字段分组，columns 下四个数组都返回空数组。

{{
  "inferred_layer": "ODS|DWD|DWS|ADS|DIM|OTHER",
  "table_type": "dimension|fact|other",
  "confidence": 0.0,
  "reasoning_steps": ["分析步骤1...", "分析步骤2..."],
  "columns": {{
    "atomic_metrics": [
      {{
        "name": "字段名",
        "data_type": "字段类型",
        "business_process": "业务过程，无法判断则为空字符串",
        "action": "动作动词，无法判断则为空字符串",
        "measure": "度量名词，无法判断则为空字符串",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "derived_metrics": [
      {{
        "name": "字段名",
        "data_type": "字段类型",
        "expression": "派生表达式，无法判断则为空字符串",
        "derived_from": ["来源字段"],
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "dimensions": [
      {{
        "name": "字段名",
        "dimension_type": "primary_key|foreign_key|date|time|status|attribute|degenerate|other",
        "data_type": "字段类型",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "others": [
      {{
        "name": "字段名",
        "role": "audit|technical|unknown|other",
        "data_type": "字段类型",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ]
  }}
}}
"""
    return prompt


def build_retry_prompt(ctx: TableContext,
                       result: TableInspectResult,
                       ddl_columns: set[str]) -> str:
    """基于校验失败结果构造重试 prompt。"""
    retry_context = {
        "validation": result.validation,
        "status": result.status,
        "ddl_columns": sorted(ddl_columns),
    }
    return build_prompt(ctx) + f"""

## 上次返回结果校验未通过
{json.dumps(retry_context, ensure_ascii=False, indent=2)}

请重新返回完整 JSON，并严格修正:
- 字段名必须来自 ddl_columns，不要编造字段。
- 同一个字段只能出现在 atomic_metrics / derived_metrics / dimensions / others 中的一个分组。
- 如果表是 DWD fact，DDL 中每个字段都必须进入且仅进入一个分组。
- 不要返回 Markdown，不要返回额外解释。
"""


def _strip_markdown_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline >= 0:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _valid_layer(value: Any) -> str:
    layer = str(value or "OTHER").upper()
    return layer if layer in VALID_LAYERS else "OTHER"


def _valid_table_type(value: Any) -> str:
    table_type = str(value or "other").strip()
    return table_type if table_type in VALID_TABLE_TYPES else "other"


def _normalize_group_item(raw: dict[str, Any], fields: tuple[str, ...]) -> dict:
    name = str(raw.get("name") or raw.get("column_name") or "").strip()
    if not name:
        return {}

    item = {"name": name}
    for field_name in fields:
        if field_name == "name":
            continue
        if field_name == "confidence":
            item[field_name] = _safe_float(raw.get(field_name))
        elif field_name == "derived_from":
            item[field_name] = _safe_list(raw.get(field_name))
        else:
            item[field_name] = str(raw.get(field_name) or "")
    return item


def _normalize_columns(raw_columns: Any) -> dict[str, list[dict[str, Any]]]:
    columns = _empty_columns()
    if not isinstance(raw_columns, dict):
        return columns

    group_fields = {
        "atomic_metrics": (
            "name",
            "data_type",
            "business_process",
            "action",
            "measure",
            "description",
            "reason",
            "confidence",
        ),
        "derived_metrics": (
            "name",
            "data_type",
            "expression",
            "derived_from",
            "description",
            "reason",
            "confidence",
        ),
        "dimensions": (
            "name",
            "dimension_type",
            "data_type",
            "description",
            "reason",
            "confidence",
        ),
        "others": (
            "name",
            "role",
            "data_type",
            "description",
            "reason",
            "confidence",
        ),
    }

    for group_name, fields in group_fields.items():
        raw_items = raw_columns.get(group_name, []) or []
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item = _normalize_group_item(raw_item, fields)
            if item:
                columns[group_name].append(item)
    return columns


def parse_response(table_name: str,
                   response: dict,
                   declared_layer: str = "") -> TableInspectResult:
    content = response.get("choices", [{}])[0].get("message",
                                                   {}).get("content",
                                                           "").strip()
    content = _strip_markdown_json(content)

    try:
        data = json.loads(content)
        return TableInspectResult(
            table_name=table_name,
            declared_layer=str(declared_layer or ""),
            inferred_layer=_valid_layer(data.get("inferred_layer")),
            table_type=_valid_table_type(data.get("table_type")),
            confidence=_safe_float(data.get("confidence")),
            reasoning_steps=list(data.get("reasoning_steps", []) or []),
            columns=_normalize_columns(data.get("columns")),
        )
    except json.JSONDecodeError as e:
        return TableInspectResult(
            table_name=table_name,
            declared_layer=str(declared_layer or ""),
            inferred_layer="OTHER",
            table_type="other",
            confidence=0.0,
            reasoning_steps=[f"JSON 解析失败: {e}\n原文: {content}"],
        )


def result_to_dict(result: TableInspectResult) -> dict[str, Any]:
    return {
        "table_name": result.table_name,
        "declared_layer": result.declared_layer,
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "confidence": result.confidence,
        "reasoning_steps": result.reasoning_steps,
        "columns": result.columns,
        "validation": result.validation,
        "status": result.status,
        "retry_count": result.retry_count,
        "is_violating_declared_layer": result.is_violating_declared_layer,
    }


def dict_to_result(data: dict[str, Any],
                   *,
                   table_name: str = "",
                   declared_layer: str = "") -> TableInspectResult:
    return TableInspectResult(
        table_name=str(data.get("table_name") or table_name),
        declared_layer=str(data.get("declared_layer") or declared_layer),
        inferred_layer=_valid_layer(data.get("inferred_layer")),
        table_type=_valid_table_type(data.get("table_type")),
        confidence=_safe_float(data.get("confidence")),
        reasoning_steps=list(data.get("reasoning_steps", []) or []),
        columns=_normalize_columns(data.get("columns")),
        validation=_normalize_validation(data.get("validation")),
        retry_count=int(data.get("retry_count", 0) or 0),
    )


def _normalize_validation(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized = {}
    for key in ("unknown_columns", "duplicate_columns", "missing_columns"):
        raw_items = value.get(key, []) or []
        if isinstance(raw_items, list):
            normalized[key] = [str(item) for item in raw_items]
    return normalized


def _extract_ddl_column_names(ddl: str) -> set[str]:
    """从 DDL 中解析字段名，用于校验 LLM 字段分组结果。"""
    if not ddl.strip():
        return set()
    try:
        import sqlglot
        from sqlglot import exp

        columns = set()
        for stmt in sqlglot.parse(ddl, dialect="doris"):
            if isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Schema):
                for col in stmt.this.expressions:
                    if isinstance(col, exp.ColumnDef):
                        columns.add(col.this.name)
        return columns
    except Exception:
        return set()


def validate_columns(result: TableInspectResult,
                     ddl_columns: set[str]) -> dict[str, list[str]]:
    """校验 LLM 返回字段是否存在、是否重复、事实表字段是否遗漏。"""
    if not ddl_columns:
        return {}

    grouped_names = []
    for group in COLUMN_GROUPS:
        for item in result.columns.get(group, []):
            grouped_names.append(str(item.get("name") or ""))

    seen = set()
    duplicates = set()
    for name in grouped_names:
        if not name:
            continue
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    returned = {name for name in grouped_names if name}
    validation = {
        "unknown_columns": sorted(returned - ddl_columns),
        "duplicate_columns": sorted(duplicates),
        "missing_columns": [],
    }
    if result.declared_layer == "DWD" and result.is_fact_table:
        validation["missing_columns"] = sorted(ddl_columns - returned)
    return validation


class TableInspector:

    def __init__(self,
                 api_key: str,
                 *,
                 model: str = "deepseek-v4-flash",
                 cache_file: Path = None,
                 max_retries: int = 1):
        self.api_key = api_key
        self.model = model
        self.cache_file = cache_file
        self.max_retries = max(0, int(max_retries))
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if self.cache_file and self.cache_file.exists():
            try:
                self.cache = json.loads(
                    self.cache_file.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}

    def _save_cache(self):
        if self.cache_file:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(self.cache,
                                                  ensure_ascii=False,
                                                  indent=2),
                                       encoding="utf-8")

    def _compute_hash(self, ctx: TableContext) -> str:
        # 缓存 hash 需要包含所有影响 LLM 判断的特征与 prompt schema 版本。
        content = (
            f"{PROMPT_VERSION}|{ctx.table_name}|{ctx.layer}|{ctx.ddl}|"
            f"{ctx.etl_sql}|{ctx.upstream_tables}|{ctx.downstream_tables}|"
            f"{ctx.depth_from_ods}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _call_api(self, prompt: str) -> str:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.0
        }

        req = urllib.request.Request(url,
                                     data=json.dumps(data).encode("utf-8"),
                                     headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"DeepSeek API 调用失败: {e}")

    def inspect(self, ctx: TableContext) -> TableInspectResult:
        current_hash = self._compute_hash(ctx)

        if ctx.table_name in self.cache:
            cached_data = self.cache[ctx.table_name]
            if cached_data.get("hash") == current_hash:
                return dict_to_result(cached_data.get("result", {}),
                                      table_name=ctx.table_name,
                                      declared_layer=ctx.layer)

        ddl_columns = _extract_ddl_column_names(ctx.ddl)
        prompt = build_prompt(ctx)
        result = None
        for attempt in range(self.max_retries + 1):
            try:
                resp_str = self._call_api(prompt)
                resp_json = json.loads(resp_str)
            except Exception as e:
                result = TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="OTHER",
                    table_type="other",
                    confidence=0.0,
                    reasoning_steps=[f"分类异常: {str(e)}"],
                    retry_count=attempt,
                )
                if attempt >= self.max_retries:
                    break
                continue

            result = parse_response(ctx.table_name, resp_json, ctx.layer)
            result.retry_count = attempt
            result.validation = validate_columns(result, ddl_columns)
            if result.status == "passed" or attempt >= self.max_retries:
                break
            prompt = build_retry_prompt(ctx, result, ddl_columns)

        self.cache[ctx.table_name] = {
            "hash": current_hash,
            "result": result_to_dict(result),
        }
        self._save_cache()

        return result

    def inspect_batch(
            self, contexts: list[TableContext]) -> list[TableInspectResult]:
        results = []
        for ctx in contexts:
            try:
                results.append(self.inspect(ctx))
            except Exception as e:
                results.append(
                    TableInspectResult(
                        table_name=ctx.table_name,
                        declared_layer=ctx.layer,
                        inferred_layer="OTHER",
                        table_type="other",
                        confidence=0.0,
                        reasoning_steps=[f"分类异常: {str(e)}"]))
        return results
