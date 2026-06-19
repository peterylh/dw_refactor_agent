# Assess 规则引擎设计原则

本文记录 `assess` 规则引擎与规则实现的设计边界，供后续新增或调整评估规则时参考。目标是让系统通过增加规则扩展能力，而不是在规则引擎中为具体规则增加特化逻辑。

## 核心边界

规则执行由三层组成：

| 层级 | 责任 | 不应承担的责任 |
| --- | --- | --- |
| 规则引擎 | 注册规则、按 `domain + target` 分组、按选择器启停规则、调用 `evaluate(target, rule_context)`、标准化返回值 | 识别具体业务规则、为某条规则准备专用数据、决定业务是否违规 |
| 维度 scorer | 从 `AssessmentContext` 准备本维度的 target 集合和通用 `rule_context`，组织同一维度内的规则组 | 计算某条规则的违规结论，或把单规则判断结果塞进 target/context |
| 规则 | 判断当前 target 是否适用，读取 `rule_context` 中的通用事实或查询能力，返回检查结果 | 修改上下文、执行外部副作用、依赖引擎中的规则特化 |

规则引擎必须保持业务无关。`RuleRunner` 不应出现 `MODEL_*`、`NAMING_*`、`METADATA_*` 等具体规则 ID 的业务分支。

## Target 与 Rule Context

`target` 表示当前正在检查的最小对象，例如一张表、一条依赖边、一个 Task 或一个文件资产。

`rule_context` 表示规则执行时可读取的上下文。它可以包含：

- 跨 target 复用的索引，如 `table_layers`、`table_edges`、`models`。
- 只读配置，如 `naming_config`、`business_domain_config`。
- 只读懒加载查询函数，如 `design_facts_for(table_name)`、`upstream_tables_for(table_name)`。

`rule_context` 不应包含某条规则的违规结论，例如：

- `is_dim_info`
- `invalid_upstream_tables`
- `reason_codes`
- `has_xxx_violation`

这些结论应由规则自己在 `evaluate()` 中计算。

## 通用事实的尺度

可能被多条规则复用、且描述对象事实本身的信息，可以提前放入 `rule_context` 或以懒加载函数提供。

适合放入 `rule_context`：

- 表层级索引：`table_layers`
- 血缘边索引：`table_edges`
- 模型元数据：`model_metadata`
- 资产目录：`asset_catalog`
- 加工形态事实查询：`design_facts_for(table_name)`
- 上游表查询：`upstream_tables_for(table_name)`

不适合放入 `rule_context`：

- 只服务某条规则的布尔判断。
- 已经带有治理结论的字段。
- 需要规则解释后才成立的派生结果。

如果一个事实计算成本较高，优先提供带缓存的 getter，而不是在构造所有 target 时提前计算。

## Evaluate 返回值语义

规则的 `evaluate()` 接口为：

```python
def evaluate(self, target: dict, rule_context: dict):
    ...
```

返回值语义：

| 返回值 | 含义 | 是否进入 checks |
| --- | --- | --- |
| `None` | 当前规则不适用于该 target，或无需产生检查项 | 否 |
| `dict` | 一条检查结果 | 是 |
| `list[dict]` | 多条检查结果 | 是 |

检查结果中的 `passed=True` 表示规则适用且通过；`passed=False` 表示规则适用但失败。`None` 不等同于通过，它表示不参与检查。

适用范围过滤应放在规则内部，例如：

```python
def evaluate(self, target: dict, rule_context: dict) -> dict | None:
    if target["layer"] != "DWS":
        return None
    ...
```

## 新增规则流程

新增一条规则时，优先按以下顺序处理：

1. 在对应维度的规则定义文件中新增 `AssessRule` 子类。
2. 在 `assess/scoring/config.py` 中新增规则元信息。
3. 将规则类加入该维度的 `*_RULE_CLASSES` 列表。
4. 如果现有 target 或 `rule_context` 已能提供所需事实，只改规则本身。
5. 如果缺少的是通用事实，优先在维度 scorer 中加入通用 context key 或懒加载 getter。
6. 如果缺少的是规则私有结论，不要加入 scorer，在规则内部计算。
7. 增加聚焦单测，覆盖不适用、通过、失败场景。

只有当一类新 target 或一类通用事实会被多条规则复用时，才调整维度 scorer。

## 维度 Scorer 的规则组织

维度 scorer 可以按 target 类型或规则组组织执行，例如：

- 表规则、字段规则、Task 规则分开准备 target。
- 同一维度中，不同 target 形态可以分开运行，例如表资产 target 与文件资产 target。
- 依赖可选输入的规则可以只在输入存在时运行，例如有外部巡检结果时才构造对应 target。

这种组织属于维度层职责。它不应下沉到 `RuleRunner`，也不应变成某条规则的特殊通道。

当某个维度目前只有一条规则时，scorer 中可能有针对该规则的跳过逻辑以避免无意义计算。后续如果该维度扩展多条规则，应改为统一的 target/context + runner 模式。

## 不建议的实现方式

避免以下模式：

- 在 `RuleRunner` 中判断具体规则 ID。
- 为某条规则在 target 中加入 `is_xxx`、`xxx_violation` 等结论字段。
- 因单条规则需要而无条件为所有 target 计算高成本 facts。
- 在规则中修改 `rule_context` 或项目资产。
- 用字段名黑名单替代结构化血缘或 SQL 事实，除非该规则明确就是命名/词表规则。

保持这些边界后，后续新增规则通常只需要新增规则类、规则元信息和测试。
