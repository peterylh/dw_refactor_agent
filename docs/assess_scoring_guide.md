# Assess 评分标准

本文总结 `assess/assess_middle_layer.py` 当前使用的评分维度、默认权重和各维度打分口径。这里描述的是实现现状，后续调整评分逻辑时应同步更新本文。

## 总体评分

`assess` 默认输出 7 个维度：

| 维度 | 默认权重 | 说明 |
| --- | ---: | --- |
| `reuse` | 18% | 中间层表下游复用度 |
| `depth` | 18% | ADS 链路经过的中间层深度 |
| `model_design` | 18% | 模型设计、层级依赖、事实表粒度和 LLM 一致性 |
| `naming` | 18% | 表、字段、指标、实体语义和文件命名规范 |
| `asset_completeness` | 9% | DDL、Model、Task、血缘产出闭环完整性 |
| `metadata_health` | 9% | `models/*.yaml` 元数据结构自洽性 |
| `code_quality` | 10% | Task SQL 代码质量 |

总体分计算方式：

```text
overall_score = sum(维度权重 * 维度得分) / 选中维度权重之和
```

默认权重来自 `assess/scoring/config.py` 的 `DEFAULT_WEIGHTS`。CLI 支持用 `--reuse-weight`、`--depth-weight`、`--model-design-weight`、`--naming-weight`、`--asset-completeness-weight`、`--metadata-health-weight`、`--code-quality-weight` 覆盖；覆盖后会自动归一化。`--architecture-weight` 和 `--architecture` 是历史兼容别名，等同于 `model_design`。

当只选择部分维度运行时，整体评分只使用被选中的维度及其权重。默认输出会过滤已通过的 `checks`，只保留和 `issues` 相关的失败检查；`--include-passed-checks` 只影响输出明细，不影响得分。

## 复用度 `reuse`

评分对象：所有 `layer in (DWD, DWS, DIM)` 的中间层表。

单表得分：

```text
score = min(100, downstream_count / 3 * 100)
```

维度得分为所有中间层表单表得分的平均值；没有中间层表时为 `0.0`。

| 下游引用数 | 单表得分 | 问题等级 |
| ---: | ---: | --- |
| `>= 3` | 100 | 通过 |
| `1..2` | 33.3 或 66.7 | 低 |
| `0` | 0 | 中 |

目标下游引用数由 `REUSE_FULL_SCORE_AT = 3` 控制。

## 链路深度 `depth`

评分对象：所有 ADS 表。

对每张 ADS 表，沿上游血缘递归计算最大中间层深度。中间层只统计 `DWD`、`DWS`、`DIM`；没有声明层级的表按 `OTHER` 处理，不再按表名前缀兜底推断。

| 最大中间层深度 | 单表得分 | 说明 |
| ---: | ---: | --- |
| `2` | 100 | 理想深度 |
| `1` | 50 | 中间层不足 |
| `0` | 0 | 缺少中间层 |
| `>= 3` | 30 | 链路过长 |

维度得分为所有 ADS 表单表得分的平均值；没有 ADS 表时为 `100.0`。

## 模型设计 `model_design`

评分对象：项目血缘表与模型元数据。该维度替代旧的 `architecture` 维度，旧名称仍作为兼容别名。

扣分方式不是简单的通过率，而是按表累计违规权重：

```text
table_weight = sum(该表失败检查的严重度权重)
table_capped = min(table_weight, 3)
score = max(0, 100 * (1 - sum(table_capped) / table_count))
```

严重度权重：高=3，中=2，低=1。每张表最多按 3 分扣分，避免单表大量问题拖垮整体。`table_count` 为血缘数据中的表数量；没有表时为 `100.0`。

主要检查：

| 规则 | 口径 |
| --- | --- |
| 层级依赖方向 | 相邻上层依赖正常，如 `ODS -> DWD -> DWS -> ADS`；`DIM -> ADS` 允许。反向依赖为高，跳层依赖为中，同层依赖为低。 |
| 配置层与 LLM 推断层一致 | 仅启用 `--llm` 且有巡检结果时检查。 |
| DWD 维度表位置 | LLM 判断为 `dimension` 且配置层为 `DWD` 时记低风险问题。 |
| 配置表类型与 LLM 推断一致 | model 中已有合法 `table_type` 时检查。 |
| `data_domain` / `business_area` 与 LLM 推断一致 | 仅在对应层适用且 LLM 推断值可通过业务字典校验时检查；未配置时按低风险，不一致时按中风险。 |
| DWD fact 保持明细粒度 | DWD fact 的 Task SQL 或 typed edge 血缘不应出现 `GROUP BY` 或聚合函数。 |
| DWD fact 不配置派生/计算指标 | DWD fact 的 model 元数据不应配置 `derived_metrics` 或 `calculated_metrics`。 |
| DWD fact 包含事件键 | 列名或实体键中应存在明显事件、流水、明细类 `_id`、`_no`、`_key` 字段。 |
| DWS fact 配置 grain | DWS fact 必须配置 `grain`。 |
| DWS grain 与 SQL `GROUP BY` 一致 | 已配置 `grain` 且 SQL 有 `GROUP BY` 时，检查 grain key 与 GROUP BY 输出粒度一致。 |
| DWS fact 包含聚合逻辑 | 有作业或 typed edge 证据时，DWS fact 应出现聚合血缘。 |
| DWS SELECT 字段符合粒度 | typed edge 中的普通透传字段必须属于 `grain` 或 `GROUP BY` 来源；常量字段不参与明细泄漏判断。 |
| DIM 不配置指标分组 | DIM 或 `table_type=dimension` 的模型不应配置 `atomic_metrics`、`derived_metrics`、`calculated_metrics`。字段是否语义上像度量保留给 LLM 巡检判断，不用字段名词表硬判。 |

## 命名规范 `naming`

评分对象：中间层表的命名检查，加上 DDL、Model、Task 文件命名检查。

维度得分：

```text
score = 通过检查数 / 总检查数 * 100
```

没有任何命名检查时为 `100.0`。

表级检查只覆盖 `DWD`、`DWS`、`DIM`。当有资产目录时，只检查存在 DDL 的表；同时会检查所有解析到的 DDL、Model、Task 文件。

主要检查：

| 检查项 | 口径 |
| --- | --- |
| 表名模板 | 表名必须匹配所在层级在 `naming_config.yaml` 中配置的模板。 |
| 表名长度 | 如果配置了表名长度上限，表名长度必须不超过上限。 |
| 字段命名 | 非指标字段必须匹配通用列名或字段命名模板/前后缀规则。 |
| 原子指标命名 | 如果配置了 atomic metric 规则，`atomic_metrics` 中每个指标都必须匹配。 |
| 派生指标命名 | 如果配置了 derived metric 规则，`derived_metrics` 中每个指标都必须匹配。 |
| DWS 表名实体 | DWS 表名中的实体段必须包含于 `grain.entities`。 |
| DIM 表名实体 | DIM 表名实体必须等于 `entities.primary.code`。 |
| 表名语义段 | 适用时，表名中的 `data_domain` / `business_area` 段必须与 model 元数据一致。 |
| DDL 文件名 | DDL 文件名 stem 必须等于建表表名。 |
| Model 文件名 | Model 文件名 stem 必须等于 YAML 中的 `name`。 |
| Task 文件名 | Task 文件名 stem 必须等于该 Task 的唯一产出表。 |

## 资产完整性 `asset_completeness`

评分对象：资产目录中的 DDL、Model、Task 及血缘目标。

维度得分：

```text
score = 通过检查数 / 总检查数 * 100
```

没有任何检查项时为 `100.0`。

主要检查：

| 检查项 | 口径 |
| --- | --- |
| DDL 表存在 Model | 每张 DDL 表应有对应 `models/{table}.yaml`。 |
| 需执行 DDL 表存在 Task | 非 ODS 且非 `config.materialized: source` 的表，应有产出该表的 Task。 |
| Model 存在 DDL | 每个 Model 应有对应 DDL 表。 |
| Task 有且只有一个产出表 | 每个 Task 必须解析出且只解析出一个持久目标表。 |
| Task 产出表存在 DDL | 每个 Task 产出目标必须有 DDL。 |
| Task 产出表存在 Model | 每个 Task 产出目标必须有 Model。 |
| 目标表有且只有一个逻辑产出 Task | 同一目标表不应由多个逻辑 Task 写入。 |
| Task 血缘目标与实际产出一致 | Task 实际产出集合必须等于血缘目标集合。 |

## 元数据健康度 `metadata_health`

评分对象：`models/*.yaml` 与表字段、业务字典之间的自洽性。

维度得分：

```text
score = 通过检查数 / 总检查数 * 100
```

没有 model 元数据时直接返回 `100.0` 且无检查；有 model 但没有适用检查项时也为 `100.0`。

主要检查：

| 检查项 | 适用范围 | 口径 |
| --- | --- | --- |
| DIM 主实体 | DIM | 必须配置 `entities.primary.code`。 |
| DIM 语义主题 | DIM | `semantic_subject` 必须等于主实体 code。 |
| 实体键字段存在 | 有表字段信息且 entity 配置 `key_columns` | `entities[*].key_columns` 必须存在于表字段中。 |
| 实体关系来源 | 非主实体且配置 relationship | `relationship.from_entity` 必须等于当前模型主实体。 |
| 关联实体不重复主实体 | 非主实体 | 关联实体 code 不应等于主实体 code。 |
| grain 键字段存在 | 有表字段信息且配置 `grain.keys` | `grain.keys` 必须存在于表字段中。 |
| DWS grain.entities | DWS 或已配置 grain.entities | DWS 必须配置 `grain.entities`；已配置时引用的实体必须已定义。 |
| data_domain 有效 | 适用层级 | 必须存在于业务字典，且符合命名配置类型定义。缺失按低风险 issue。 |
| business_area 有效 | 适用层级 | 必须存在于业务字典，且符合命名配置类型定义。缺失按低风险 issue。 |

## 代码质量 `code_quality`

评分对象：`tasks/*.sql` 中可解析的建表、写入和删表语句。

维度得分：

```text
score = 通过检查数 / 总检查数 * 100
```

没有任何检查项时为 `100.0`。

主要检查：

| 检查项 | 口径 |
| --- | --- |
| 临时表名包含 `temp` 或 `tmp` | Task 内 `CREATE TABLE` 的非目标表视为中间临时表，名称必须包含 `temp` 或 `tmp`。 |
| 临时表在同一作业清理 | 临时表必须在创建后的后续语句中被 `DROP TABLE` 清理。 |
| 写入型语句不使用 `SELECT *` | `INSERT` 和 `CREATE TABLE AS SELECT` 等写入型语句必须显式列出字段；普通只读 `SELECT *` 不计入。 |

## 输出结构

每个维度统一输出：

- `score`: 维度得分。
- `rule_summary`: 按规则汇总的通过数、总数和通过率。
- `checks`: 检查项明细，默认结果中只保留失败检查；使用 `--include-passed-checks` 可输出全部检查。
- `issues`: 由失败检查生成的问题项，包含严重度、规则、目标、修复摘要和关联 `check_ids`。

严重度用于描述修复优先级；除 `model_design` 外，严重度不参与维度分数计算。
