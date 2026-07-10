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

- `warehouses/{project}/mid/ddl/`
- `warehouses/{project}/mid/tasks/`
- `warehouses/{project}/mid/models/`
- `warehouses/{project}/ads/tasks/`：仅当需要保持 ADS 输出不变而调整取数逻辑时修改

只修改 DWS/DIM/DWD 表结构；ODS 和 ADS 表结构默认保持不变。ADS SQL 可以重构，
但不能改变 ADS 表字段、类型、分区、主键或输出语义。
不要修改命名规范配置文件， 但是可以针对命名规范提出改进建议
不要修改工具代码或测试代码， 但是可以报告问题
- `src/dw_refactor_agent/lineage/`
- `src/dw_refactor_agent/execution/`
- `src/dw_refactor_agent/refactor/`
- `src/dw_refactor_agent/assessment/`
- `src/dw_refactor_agent/ddl_deriver/`
- `tests/`

## 默认不提交的派生文件

数仓资产重构默认不更新以下生成物：

- `warehouses/{project}/artifacts/lineage/lineage_data.json`
- `warehouses/{project}/artifacts/lineage/job_dag.json`
- `warehouses/{project}/artifacts/lineage/*.html`
- `warehouses/{project}/artifacts/assessment/*.json`
- `warehouses/{project}/artifacts/assessment/cache/`
- `warehouses/<project>/artifacts/refactor_runs/`

除非用户明确要求更新这些派生结果。

## 搜索与残留判断

修改前后都应使用 `rg` 搜索旧名称，专项指南会说明具体搜索词。

对残留结果逐项判断：

- 如果是当前 SQL、DDL、models 的真实引用，应继续修改
- 如果是历史文档、旧报告、生成物、缓存，可保留
- 如果是工具代码或测试代码，不要默认修改，先判断是否真的属于本次数仓资产重构

不要为了消除所有文本命中而盲目替换注释、历史说明或无关示例；是否更新注释取决于它是否描述当前逻辑。

## 默认验证

### Schema Identity

受管 DDL 使用稳定 UUID 标识表和字段。Agent 修改 DDL 时遵守：

```bash
# 新建整张表
python -m dw_refactor_agent.ddl_deriver.schema_ids init-file --file <ddl_file>

# 已有表新增字段
python -m dw_refactor_agent.ddl_deriver.schema_ids assign-column --file <ddl_file> --column <column_name>

# 完成前校验
python -m dw_refactor_agent.ddl_deriver.schema_ids validate --project <project>
```

表或字段重命名、字段属性修改必须保留原 ID。复制、拆分、合并或语义替换得到的
新表/新字段必须生成新 ID。`ddl_deriver` 和 `refactor run analyze` 只读取 ID，
不会自动补齐；缺失、非法或重复 ID 会阻断分析。

首次为项目补齐 schema identity 后，迁移前创建的 refactor run 不再具有可用的
身份基线。合并迁移后应重新开始 run：

```bash
python -m dw_refactor_agent.refactor.run start --project <project>
```

默认验证：

```bash
python -m dw_refactor_agent.lineage.lineage_extractor --project <project>
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
python -m dw_refactor_agent.lineage.refresh_lineage_html --project <project>
```

原因：刷新 HTML 是可视化生成操作，不是数仓资产重构的必要步骤。

不要默认运行：

```bash
python -m dw_refactor_agent.execution.task_run --project <project> --db-env test
```

原因：`--db-env test` 是在测试库真实执行任务，不是 dry-run。只有用户明确要求执行数据验证时才运行。

## 可选操作

用户明确要求更新可视化时，才执行：

```bash
python -m dw_refactor_agent.lineage.refresh_lineage_html --project <project>
```

用户明确要求真实执行测试库任务时，才执行：

```bash
python -m dw_refactor_agent.execution.task_run --project <project> --db-env test --job-list <job_name>
```

如果需要预览重构验证计划，应使用重构验证工具的 dry-run：

```bash
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --dry-run
```

预览前应先确认 `analyze` 是否需要指定验证分区。若验证计划包含配置了
`execution.slice` 或项目 `execution.default_slice` 的增量作业，必须先用
`--partition` 生成 `jobs_to_run[].execution_values`：

```bash
python -m dw_refactor_agent.refactor.run analyze --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --partition 2025-01-15
```

没有 `execution_values` 的 sliced incremental 作业会在 shadow-run dry-run
或真实执行阶段失败；工具不会默认使用当天日期或全局 driver value 兜底。

`jobs_to_run` 只包含本次直接修改的可执行任务及其下游任务。未修改上游仍可
出现在 `change_analysis.json` 的宽 `affected_scope` 中，但不会因此创建 QA 表
或参与重算；shadow manifest 会将其数据读取路由到生产库。verification plan
的最终锚点位于 `verification.anchor_tables`，旧 plan 不再兼容，相关 run 需要
重新执行 `analyze`。

sliced job 或无依赖 job 较多时，可显式开启 shadow-run 全局并发和
mysql 会话批量复用：

```bash
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --parallel 4 --batch-size 2
```

`--parallel` 控制 shadow-run 全局 mysql 会话并发上限：无未完成上游依赖的
ready job 可以并发执行，同一 sliced job 的 slice batch 也共享该上限。
`--batch-size` 控制每个 mysql 会话中串联执行的 slice 数。默认均为 `1`，
保持串行兼容行为。
