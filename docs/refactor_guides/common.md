# 数仓资产重构通用规则

## 目标

本指南定义数仓资产重构时的通用边界，适用于表重命名、字段重命名等常见变更。

具体重构步骤请参考同目录下的专项指南：

- [表重命名指南](table_rename.md)
- [字段重命名指南](field_rename.md)

## 适用项目

- `shop`
- `finance_analytics`

## 修改范围

只修改数仓项目资产：

- `{project}/ddl/`
- `{project}/tasks/`
- `{project}/models/`
- `{project}/data/`：仅当 ODS 表、ODS 字段或初始化数据涉及本次变更时修改

只修改 DWS/DIM/DWD 表，不修改其他资产
不要修改命名规范配置文件， 但是可以针对命名规范提出改进建议
不要修改工具代码或测试代码， 但是可以报告问题
- `lineage/`
- `exec/`
- `refact/`
- `assess/`
- `ddl_deriver/`
- `tests/`

## 默认不提交的派生文件

数仓资产重构默认不更新以下生成物：

- `lineage/lineage_data_*.json`
- `lineage/job_dag_*.json`
- `lineage/*.html`
- `assess/*_result_*.json`
- `refact/refact_metadata.json`
- `refact/verify_result.json`

除非用户明确要求更新这些派生结果。

## 搜索与残留判断

修改前后都应使用 `rg` 搜索旧名称，专项指南会说明具体搜索词。

对残留结果逐项判断：

- 如果是当前 SQL、DDL、models 的真实引用，应继续修改
- 如果是历史文档、旧报告、生成物、缓存，可保留
- 如果是工具代码或测试代码，不要默认修改，先判断是否真的属于本次数仓资产重构

不要为了消除所有文本命中而盲目替换注释、历史说明或无关示例；是否更新注释取决于它是否描述当前逻辑。

## 默认验证

默认验证：

```bash
python lineage/lineage_extractor.py --project <project>
```

这个命令用于验证 SQL 和 models 能被项目血缘解析器识别。

注意：该命令可能生成或更新 lineage JSON。默认不要把这些生成物作为数仓资产重构改动提交，除非用户明确要求。

## 不默认执行的操作

不要默认运行：

```bash
make test
```

原因：数仓资产重构通常不应该影响工具代码测试。只有修改了工具代码时，才运行
`make test`。不要直接运行裸 `pytest`，它可能使用 PATH 中的 Homebrew Python 或其他
全局解释器。

不要默认运行：

```bash
python lineage/refresh_lineage_html.py --project <project>
```

原因：刷新 HTML 是可视化生成操作，不是数仓资产重构的必要步骤。

不要默认运行：

```bash
python exec/task_run.py --project <project> --db-env test
```

原因：`--db-env test` 是在测试库真实执行任务，不是 dry-run。只有用户明确要求执行数据验证时才运行。

## 可选操作

用户明确要求更新可视化时，才执行：

```bash
python lineage/refresh_lineage_html.py --project <project>
```

用户明确要求真实执行测试库任务时，才执行：

```bash
python exec/task_run.py --project <project> --db-env test --job-list <job_name>
```

如果需要预览重构验证计划，应使用重构验证工具的 dry-run：

```bash
python refact/verify_run.py --metadata refact/refact_metadata.json --dry-run
```
