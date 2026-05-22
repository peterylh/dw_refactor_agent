import json
import hashlib
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from assess.context_builder import TableContext


@dataclass
class ClassifyResult:
    table_name: str
    inferred_layer: str  # "ODS" | "DWD" | "DWS" | "ADS" | "DIM" | "OTHER"
    table_type: str      # "dimension" | "fact" | "other"
    confidence: float
    reasoning_steps: list[str]
    is_violating_current_name: bool


def build_prompt(ctx: TableContext) -> str:
    prompt = f"""你是一位资深数据仓库架构师。你的任务是根据给定的表结构、ETL 加工逻辑和血缘关系，客观推断这张表真实应该归属的数仓分层，并判断它的物理表类型（维度表/事实表）。

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

## 思考步骤 (Chain of Thought)
1. 首先分析 ETL_SQL 中是否包含 GROUP BY 等聚合操作，如果有，排除 DWD 和 ODS。
2. 观察下游被引用次数。如果为 0，大概率是 ADS；如果 > 1，倾向于 DWS 或 DWD。
3. 判断是否为 dimension（主键是否为实体属性）。
4. 结合 DDL 中的字段特征（如是否存在大量 DECIMAL 度量），最终得出结论。

请严格返回 JSON 格式数据:
{{"inferred_layer": "ODS|DWD|DWS|ADS|DIM|OTHER", "table_type": "dimension|fact|other", "confidence": 0.0~1.0, "reasoning_steps": ["分析步骤1...", "分析步骤2..."], "is_violating_current_name": true/false}}
"""
    return prompt


def parse_response(table_name: str, response: dict) -> ClassifyResult:
    content = response.get("choices", [{}])[0].get("message",
                                                   {}).get("content",
                                                           "").strip()

    # Handle markdown wrapped JSON
    if content.startswith("```json"):
        content = content.replace("```json\n", "").replace("```json", "")
        if content.endswith("```"):
            content = content[:-3].strip()

    try:
        data = json.loads(content)
        return ClassifyResult(table_name=table_name,
                              inferred_layer=data.get("inferred_layer", "OTHER"),
                              table_type=data.get("table_type", "other"),
                              confidence=float(data.get("confidence", 0.0)),
                              reasoning_steps=data.get("reasoning_steps", []),
                              is_violating_current_name=bool(data.get("is_violating_current_name", False)))
    except json.JSONDecodeError as e:
        return ClassifyResult(table_name=table_name,
                              inferred_layer="OTHER",
                              table_type="other",
                              confidence=0.0,
                              reasoning_steps=[f"JSON 解析失败: {e}\n原文: {content}"],
                              is_violating_current_name=False)


class TableClassifier:

    def __init__(self,
                 api_key: str,
                 *,
                 model: str = "deepseek-v4-flash",
                 cache_file: Path = None):
        self.api_key = api_key
        self.model = model
        self.cache_file = cache_file
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
        # 缓存 hash 需要包含所有影响 LLM 判断的特征
        content = f"{ctx.ddl}|{ctx.etl_sql}|{ctx.upstream_tables}|{ctx.downstream_tables}|{ctx.depth_from_ods}"
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

    def classify(self, ctx: TableContext) -> ClassifyResult:
        current_hash = self._compute_hash(ctx)

        if ctx.table_name in self.cache:
            cached_data = self.cache[ctx.table_name]
            if cached_data.get("hash") == current_hash:
                res = cached_data.get("result", {})
                return ClassifyResult(table_name=ctx.table_name,
                                      inferred_layer=res.get(
                                          "inferred_layer", "OTHER"),
                                      table_type=res.get("table_type", "other"),
                                      confidence=res.get("confidence", 0.0),
                                      reasoning_steps=res.get("reasoning_steps", []),
                                      is_violating_current_name=res.get("is_violating_current_name", False))

        prompt = build_prompt(ctx)
        resp_str = self._call_api(prompt)
        resp_json = json.loads(resp_str)
        result = parse_response(ctx.table_name, resp_json)

        # Save to cache
        self.cache[ctx.table_name] = {
            "hash": current_hash,
            "result": {
                "table_name": result.table_name,
                "inferred_layer": result.inferred_layer,
                "table_type": result.table_type,
                "confidence": result.confidence,
                "reasoning_steps": result.reasoning_steps,
                "is_violating_current_name": result.is_violating_current_name
            }
        }
        self._save_cache()

        return result

    def classify_batch(self,
                       contexts: list[TableContext]) -> list[ClassifyResult]:
        results = []
        for ctx in contexts:
            try:
                res = self.classify(ctx)
                results.append(res)
            except Exception as e:
                results.append(
                    ClassifyResult(table_name=ctx.table_name,
                                   inferred_layer="OTHER",
                                   table_type="other",
                                   confidence=0.0,
                                   reasoning_steps=[f"分类异常: {str(e)}"],
                                   is_violating_current_name=False))
        return results
