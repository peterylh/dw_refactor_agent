# 当前命名配置语法说明

本文说明当前 `naming_config.yaml` 的配置语法和匹配方式。它描述的是现有 DSL，不是新的 v2 配置格式。命名判断以配置文件中的 `types`、`rules` 和 `bindings` 为准。

## 配置结构

命名配置主要由三部分组成：

- `types`: 定义可复用的命名类型。类型可以配置 `allow` 枚举值，也可以配置 `patterns` 正则。
- `rules`: 定义表名、字段名、指标名等规则表达式。
- `bindings`: 把规则绑定到具体对象类型，例如 DWD 表、DWS 表、字段、原子指标、派生指标。

示例：

```yaml
types:
  COLUMN_IDENTIFIER:
    label: 字段标识符
    patterns:
      - "^[A-Z][A-Z0-9_]{0,14}$"

rules:
  COLUMN_DEFAULT:
    desc: 默认字段命名大写标识符，长度小于16
    expr: "$COLUMN_IDENTIFIER"

bindings:
  column:
    rules:
      - "@COLUMN_DEFAULT"
```

## type 语义

`types` 定义命名片段的取值约束。规则表达式里通过 `$TYPE_NAME` 引用这些类型。

`allow` 表示有限枚举，实际值必须完全等于其中一个值。

```yaml
TIME_PERIOD:
  allow:
    - D
    - W
    - M
```

`patterns` 表示正则列表，实际值只要匹配任意一个正则即可。

```yaml
BIZ_PROCESS:
  patterns:
    - "^[A-Z][A-Z0-9]*$"
```

同一个 type 同时配置 `allow` 和 `patterns` 时，二者是 OR 关系。先尝试枚举匹配，必要时再尝试正则匹配。

`allow` 也可以从 `dictionaries` 装载：

```yaml
BUSINESS_AREA_CODE:
  allow:
    dictionary: business_areas
    value_field: code
```

项目级 `business_taxonomy.yaml` 中的 `data_domains` 和 `business_areas`
会在加载命名配置时合并进 `dictionaries`。因此业务域/板块主数据应优先维护在
`warehouses/{project}/business_taxonomy.yaml`，`naming_config.yaml` 只需要通过
`dictionary` 引用这些字典。

## rule expr 语义

规则通过 `expr` 描述。表达式可以按片段理解，每个片段属于以下几类：

- 固定字面量：未加 `$` 或 `@` 的文本。
- 类型引用：以 `$` 开头，引用 `types` 中的类型。
- 规则引用：以 `@` 开头，引用另一个命名规则，常用于指标规则组合。

### 字面量

未加 `$` 的值是固定文本。

```yaml
expr: ["_", M, "$BUSINESS_AREA_CODE"]
```

其中 `M` 是 literal，`$BUSINESS_AREA_CODE` 是 type。

### 分隔符

列表表达式的第一个元素如果是 `"_"` 或 `""`，它不是业务 segment，而是连接后续元素的分隔符控制项。

```yaml
expr: ["_", M, "$BUSINESS_AREA_CODE", "$DATA_DOMAIN_ID"]
```

表示后续元素用 `_` 连接，等价于：

```text
M_{BUSINESS_AREA_CODE}_{DATA_DOMAIN_ID}
```

如果列表第一个元素不是 `"_"` 或 `""`，默认也使用 `_` 连接。

```yaml
expr: [M, "$BUSINESS_AREA_CODE"]
```

等价于：

```text
M_{BUSINESS_AREA_CODE}
```

### 空字符串分隔符

`""` 表示后续元素之间不插入分隔符，常用于粒度后缀拼接。

```yaml
expr: ["_", M, "$BIZ_PROCESS", ["", "$TIME_PERIOD", "$DWD_GRANULARITY"]]
```

内层 `["", "$TIME_PERIOD", "$DWD_GRANULARITY"]` 表示：

```text
{TIME_PERIOD}{DWD_GRANULARITY}
```

如果 `TIME_PERIOD=D`、`DWD_GRANULARITY=I`，拼出来是 `DI`，不是 `D_I`。

完整表达式类似：

```text
M_{BIZ_PROCESS}_{TIME_PERIOD}{DWD_GRANULARITY}
```

### 直接拼接

当表达式使用空字符串分隔符时，后续片段会和左侧片段直接拼接，不额外插入 `_`。

示例：

```yaml
expr: ["", "$TIME_PERIOD", "$DWD_GRANULARITY"]
```

等价于：

```text
{TIME_PERIOD}{DWD_GRANULARITY}
```

这里 `DWD_GRANULARITY` 会直接接在 `TIME_PERIOD` 后面。

### 可选段

segment 名称以 `?` 结尾表示可选。

```yaml
expr: ["_", "$PREFIX?", "$ENTITY"]
```

如果 `PREFIX` 没有匹配成功，系统会跳过它并继续匹配后续片段。

### 重复段

segment 表达式支持有限重复：

```yaml
expr: ["_", I, "$BUSINESS_AREA_CODE", "$ENTITY{1,2}", "$METRICS_DESC"]
```

`$ENTITY{1,2}` 会展开成多个候选模板，优先尝试较长重复次数。

表名和字段名规则要求重复上限是有限值。`{1,}` 这种无上限重复只用于指标规则。

## 指标规则

指标规则也通过 `expr` 描述，可以引用普通 type，也可以用 `@RULE` 引用另一个指标规则。分隔符由表达式写法决定，当前项目示例使用 `_`。

```yaml
rules:
  ATOMIC_METRIC:
    expr: ["_", "$ACTION_VERB", "$MEASURE_NOUN"]

  DERIVED_METRIC:
    expr: ["_", "$METRIC_TIME_PERIOD", "$METRIC_MODIFIER{1,}", "@ATOMIC_METRIC"]
```

在指标规则中：

- `$TYPE` 匹配一个 type。
- `@RULE` 引用另一个指标规则。
- `{min,max}` 控制重复次数。
- `{1,}` 表示至少重复一次且无上限。

## 绑定规则

`bindings.table` 把规则绑定到模型层级。

```yaml
bindings:
  table:
    DWD:
      - "@TABLE_DWD"
```

`bindings.column` 把规则绑定到普通字段。`allow` 中的字段名直接视为通用列名。

```yaml
bindings:
  column:
    allow:
      - ETL_TIME
      - SNAPSHOT_DATE
    rules:
      - "@COLUMN_DEFAULT"
```

`bindings.metric` 把规则绑定到指标类型。

```yaml
bindings:
  metric:
    atomic: "@ATOMIC_METRIC"
    derived: "@DERIVED_METRIC"
```

## 表达式匹配理解

理解一条表达式时，可以按从左到右的业务顺序阅读：固定字面量必须原样出现，`$TYPE` 必须满足对应 type 的 `allow` 或 `patterns`，内层 `["", ...]` 表示片段直接拼接。

示例：

```yaml
expr: ["_", M, "$BUSINESS_AREA_CODE", "$DATA_DOMAIN_ID", "$BIZ_PROCESS", ["", "$TIME_PERIOD", "$DWD_GRANULARITY"]]
```

输入：

```text
M_SHOP_04_ORDER_DI
```

大致匹配过程：

1. `M` 匹配 literal `M`。
2. `_` 匹配分隔符 literal `_`。
3. `SHOP` 匹配 `BUSINESS_AREA_CODE` 枚举。
4. `04` 匹配 `DATA_DOMAIN_ID` 枚举。
5. `DI` 的右侧 `I` 匹配 `DWD_GRANULARITY`。
6. `D` 匹配 `TIME_PERIOD`。
7. 中间 `ORDER` 匹配 `BIZ_PROCESS` 正则。

如果输入是：

```text
dwd_customer
```

第一段固定字面量 `M` 就无法匹配，表名模板检查失败。

## 调试命令

查看某个项目的结构化诊断：

```bash
PYTHONPATH=src python -c "from dw_refactor_agent.config import get_naming_config; import json; nc=get_naming_config('shop'); print(json.dumps(nc.diagnose_table_name('dwd_customer', {'name': 'dwd_customer', 'layer': 'DWD'}), ensure_ascii=False, indent=2))"
```

字段诊断：

```bash
PYTHONPATH=src python -c "from dw_refactor_agent.config import get_naming_config; import json; nc=get_naming_config('shop'); print(json.dumps(nc.diagnose_column_name('customer_id'), ensure_ascii=False, indent=2))"
```

指标诊断：

```bash
PYTHONPATH=src python -c "from dw_refactor_agent.config import get_naming_config; import json; nc=get_naming_config('shop'); print(json.dumps(nc.diagnose_metric_name('pay_amt', metric_kind='atomic'), ensure_ascii=False, indent=2))"
PYTHONPATH=src python -c "from dw_refactor_agent.config import get_naming_config; import json; nc=get_naming_config('shop'); print(json.dumps(nc.diagnose_metric_name('7D_OLD_PAY_AMT', metric_kind='derived'), ensure_ascii=False, indent=2))"
```

## 诊断输出字段

诊断输出用于排查某个名称为什么没有匹配配置规则。它会透出：

- 实际名称。
- 使用的规则名和规则描述。
- 原始 `expr`。
- 每个 type 的 `allow`、`patterns`、字典来源和描述。
- 失败的片段、期望值、实际剩余字符串。

诊断不会内置判断“必须大写”或“必须小写”。如果字段规则配置成小写正则，诊断会展示小写正则；如果字段规则配置成大写正则，诊断会展示大写正则。
