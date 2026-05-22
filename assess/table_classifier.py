import json
import hashlib
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from assess.context_builder import TableContext


@dataclass
class ClassifyResult:
    table_name: str
    table_type: str  # "dimension" | "fact" | "other"
    confidence: float
    reason: str


def build_prompt(ctx: TableContext) -> str:
    prompt = f"""你是一位资深数仓架构师。请根据以下信息判断该表是"维度表(dimension)"、"事实表(fact)"还是"其他(other)"。

## 判断标准
- dimension: 维度表。描述业务实体属性(如客户、商品、门店), 缓慢变化, 被其他表引用做 JOIN 关联。
- fact: 事实表。记录业务事件/交易(如订单、销售), 包含可聚合度量字段, 通常有时间分区。也包含 DWS 层的汇总事实表。
- other: 其他类型。如桥接表、纯映射表等不属于上述两类的表。

## 表信息
表名: {ctx.table_name}
分层: {ctx.layer}

## DDL
{ctx.ddl}

"""
    if ctx.etl_sql:
        prompt += f"## ETL 加工逻辑\n{ctx.etl_sql}\n\n"

    prompt += f"""## 血缘关系
上游表: {', '.join(ctx.upstream_tables) if ctx.upstream_tables else '无'}
下游表: {', '.join(ctx.downstream_tables) if ctx.downstream_tables else '无'}

请严格返回 JSON 格式数据:
{{"table_type": "dimension|fact|other", "confidence": 0.0~1.0, "reason": "判断依据(50字内)"}}
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
                              table_type=data.get("table_type", "other"),
                              confidence=float(data.get("confidence", 0.0)),
                              reason=data.get("reason", ""))
    except json.JSONDecodeError as e:
        return ClassifyResult(table_name=table_name,
                              table_type="other",
                              confidence=0.0,
                              reason=f"JSON 解析失败: {e}\n原文: {content}")


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
        content = f"{ctx.ddl}|{ctx.etl_sql}"
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
                                      table_type=res.get(
                                          "table_type", "other"),
                                      confidence=res.get("confidence", 0.0),
                                      reason=res.get("reason", ""))

        prompt = build_prompt(ctx)
        resp_str = self._call_api(prompt)
        resp_json = json.loads(resp_str)
        result = parse_response(ctx.table_name, resp_json)

        # Save to cache
        self.cache[ctx.table_name] = {
            "hash": current_hash,
            "result": {
                "table_name": result.table_name,
                "table_type": result.table_type,
                "confidence": result.confidence,
                "reason": result.reason
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
                                   table_type="other",
                                   confidence=0.0,
                                   reason=f"分类异常: {str(e)}"))
        return results
