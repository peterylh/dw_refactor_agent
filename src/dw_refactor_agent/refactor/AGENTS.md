# Refactor 模块开发说明

## 适用范围

本文件适用于 `src/dw_refactor_agent/refactor/` 下的重构验证代码，以及
`warehouses/{project}/artifacts/refactor_runs/` 产物的生成和消费逻辑。
修改 CLI、变更范围推导、验证计划、SQL 路由、旁路执行、结果对比或产物结构前，
应先阅读本文件。

数仓资产本身的重构规则仍以 `docs/refactor_guides/` 为准：

- 通用规则：`docs/refactor_guides/common.md`
- 表重命名：`docs/refactor_guides/table_rename.md`
- 字段重命名：`docs/refactor_guides/field_rename.md`

受管 DDL 的 `table_id` / `column_id` 约束见项目根 `AGENTS.md`。schema identity、
仓库资产路径或基线解析规则发生迁移后，旧 run 不应继续复用，必须重新执行
`start`。

## 模块职责

- `run.py`：统一 CLI，串联 `start`、`analyze`、`shadow-run`、`compare`。
- `session.py`：创建 run 目录、维护 `manifest.json` 和逻辑产物名到相对路径的映射。
- `incremental_lineage.py`：生成 run 内的血缘数据与 task cache，复用未变化任务缓存。
- `change_analysis.py`：比较基线与当前资产，计算直接表、下游表、评估范围和候选锚点。
- `issue_diff.py`：按稳定 fingerprint 比较基线全量评估与当前范围评估的问题变化。
- `verification_plan.py`：推导 DDL 变化、最小作业重算集合、执行值、验证锚点与 checks。
- `shadow_scope.py`：表示并合并旁路读取、写入和预填充所需的行范围。
- `shadow_manifest.py`：运行时编译表路由、producer、作业依赖、prefill action、blocker 与 warning。
- `shadow_rewrite.py`：按编译后的路由上下文重写 SQL 表引用，生产读穿与 QA 读写规则以此处为准。
- `shadow_run.py`：重建 QA 库、建表、预填充必要数据、应用 DDL 并按 DAG 执行作业。
- `compare.py`：按 plan 中的 checks 对比生产库与 QA 库的行数或逐行数据。

表层级只读取模型 YAML 的 `layer`，不得通过表名前缀兜底推断。表名、字段名、
catalog 和 database/schema 的内部匹配遵循血缘模块的大小写不敏感规则。

## 标准工作流

统一入口为 `python -m dw_refactor_agent.refactor.run`，支持项目来自
`PROJECT_CONFIG`；当前仓库包括 `shop` 和 `finance_analytics`。

```bash
# 1. 修改前固化基线
python -m dw_refactor_agent.refactor.run start --project <project>

# 2. 修改后刷新当前血缘、评估、变更分析与验证计划
python -m dw_refactor_agent.refactor.run analyze \
  --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json \
  --partition 2025-01-15

# 3. 先预览，再执行旁路验证
python -m dw_refactor_agent.refactor.run shadow-run \
  --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json \
  --dry-run
python -m dw_refactor_agent.refactor.run shadow-run \
  --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json

# 4. 对比生产与 QA 结果
python -m dw_refactor_agent.refactor.run compare \
  --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json \
  --method all
```

### start

`start` 记录当前 Git branch、短 commit 和 dirty 状态，生成基线血缘、task cache
与全项目 assessment。应在重构修改前运行；基线产物在同一 run 中视为只读快照。
dirty worktree 可以创建 run，但 `base_git.dirty=true` 会保留这一事实，后续解释
changed files 时必须考虑未提交基线修改。

### analyze

`analyze` 以 manifest 记录的基线 commit 和 baseline 产物为输入，刷新当前血缘、
变更范围、范围 assessment、issue diff 和 verification plan。它可以重复运行；每次
都会更新 `current/`、`analysis/` 与 `verification/plan.json`。

若 `jobs_to_run` 中包含配置了 `execution.slice` 或项目 `execution.default_slice`
的增量作业，必须通过 `--partition` 提供验证分区。planner 将其展开为作业的
`execution_values`；shadow-run 不使用当天日期或全局 driver value 兜底。仅当计划
不包含 sliced incremental 作业时才可省略 `--partition`。

`affected_scope` 是评估和验证推导使用的宽影响范围，不等于执行范围。
`jobs_to_run` 只从直接变化表和下游表选择可执行作业，并按拓扑排序；未修改上游
即使属于评估范围，也不应仅因此进入旁路重算。

### shadow-run

先用 `--dry-run` 检查编译后的路由、prefill、DDL 与作业调用。常用执行参数还包括：

- `--parallel`：全局 MySQL 并发度，默认 `1`。
- `--batch-size`：每个 MySQL session 执行的 slice invocation 数，默认 `1`。
- `--timing-detail` / `--profile`：在结果中记录 invocation 级耗时。

实际执行顺序为：

1. 编译 shadow manifest，发现 blocker 时停止。
2. Phase 0 重建 QA 库。
3. Phase 1 用 `baseline_ddl` 创建必要的基线表。
4. 按 manifest 的 `prefill_actions` 从生产库预填充自读、DDL-only 等必要数据。
5. Phase 2 应用 `ddl_changes`。
6. Phase 3 按 DAG 运行 `jobs_to_run`。

SQL 路由遵循“最小重算”：ODS、未变化的中间结果和无需 QA materialization 的关系
从生产库读取；已由本次计划重算且已 ready 的中间结果从 QA 库读取；作业输出统一
写入 QA 库。不要通过复制全部生产数据来绕过 manifest 路由和 prefill 计算。

### compare

`compare` 消费 `verification.checks`，支持 `--method count|row_compare|all`、
`--sample` 和 `--precision`。`verification.compare_anchors` 提供时间列、粒度与锚点值；
缺少可用时间粒度时，planner 可能生成全表比较 warning。

`row_compare` 的排除列在 analyze 阶段从
`warehouses/{project}/warehouse.yaml` 的 `verification.row_compare` 写入最终 check：

- 项目级 `exclude_columns` 是默认值。
- `tables.<table>.exclude_columns` 覆盖项目级配置。
- 表级空列表表示全列比较。
- 兼容旧 plan 时，缺少该字段默认忽略 `etl_time`。

## Refactor run 输出物

默认输出根目录为：

```text
warehouses/{project}/artifacts/refactor_runs/{run_id}/
├── manifest.json
├── baseline/
│   ├── lineage_data.json
│   ├── task_lineage_cache.json
│   └── assess_result.json
├── current/
│   ├── lineage_data.json
│   ├── task_lineage_cache.json
│   └── assess_result.json
├── analysis/
│   ├── change_analysis.json
│   └── issue_diff.json
└── verification/
    ├── plan.json
    ├── shadow_run_result.json
    └── compare_result.json
```

后三个 verification 文件按阶段生成，尚未运行相应阶段时可以不存在。

### manifest.json

run 的稳定入口和产物索引，记录：

- `run_id`、`project`、仓库绝对 `root` 与 `created_at`。
- `base_git`：基线创建时的 branch、短 commit、dirty 状态。
- `artifacts`：逻辑产物键到 run 内相对路径的映射。

后续命令只要求传入 manifest，不应在调用方重新拼装产物路径。调整产物键或路径时，
必须同步 `session.py`、所有消费者和相关测试，并明确旧 manifest 的兼容策略。

### baseline/

由 `start` 生成，代表重构前冻结事实：

- `lineage_data.json`：基线字段/表/任务血缘。
- `task_lineage_cache.json`：基线任务解析缓存，也作为首次 analyze 的增量缓存来源。
- `assess_result.json`：基线全项目 assessment，带 `assessment_mode=full`。

同一 run 内不得由 analyze 覆盖 baseline。资产布局、schema identity 或解析语义变化
导致基线不可比时，应新建 run，而不是手工修改这些文件。

### current/

由每次 `analyze` 重建，代表当前工作区状态：

- `lineage_data.json`：当前血缘快照。
- `task_lineage_cache.json`：当前任务缓存；下一次 analyze 优先复用它。
- `assess_result.json`：受影响范围 assessment，通常带 `assessment_mode=scoped`；
  没有相关变化时标记为 `no_changes`。

### analysis/

由每次 `analyze` 重建：

- `change_analysis.json`：changed files/assets、血缘 diff、rename mapping 和
  `affected_scope`。其中 direct/downstream 驱动最小重算，assessment tables/tasks
  驱动范围评估，候选 anchor 供 verification planner 选择最终锚点。
- `issue_diff.json`：基线与当前 assessment 问题的新增、解决、持续等差异；它是质量
  变化解释，不是待执行作业列表。

### verification/

- `plan.json`：由 `analyze` 生成，是 shadow-run 与 compare 的共同输入。核心字段包括
  `changes`、`baseline_ddl`、`ddl_changes`、`jobs_to_run` 与 `verification`。
  `verification` 内含最终 `anchor_tables`、`compare_anchors`、checks、block status、
  warning 和必要的 metadata error。
- `shadow_run_result.json`：每次 shadow-run（包括 dry-run）覆盖写入，记录模式、状态、
  各 phase、作业/调用与可选耗时详情。运行时 shadow manifest 不单独落盘；其
  JSON 可序列化摘要嵌入本结果的 `shadow_manifest` 字段。
- `compare_result.json`：每次 compare 覆盖写入，记录整体通过状态及各 count /
  row_compare 校验结果。没有合法数据锚点或锚点状态 blocked 时，结果会明确失败原因。

## 修改与验证要求

- 修改 CLI 参数时同步更新本文件、根 `AGENTS.md` 的摘要命令和 CLI 测试。
- 修改 manifest artifact key、plan/result 字段或目录结构时，先搜索所有读写方；
  不要只改 producer。旧 run 是否兼容必须有明确测试。
- 修改范围选择时分别验证 `affected_scope`、`jobs_to_run` 和最终 anchor，避免把宽评估
  范围误当执行范围。
- 修改 SQL 路由、prefill 或调度时覆盖 dry-run、实际执行、self-read、DDL-only、
  sliced incremental、表重命名和大小写混用场景。
- 修改 compare 时覆盖 anchor partition、全表降级、exclude columns 和 precision。
- 本地测试遵循根 `AGENTS.md`：使用 `make test` 或显式 conda Python，不运行裸
  `pytest`。至少执行受影响的 focused tests；产物 schema 或公共流程变化时再运行
  完整非 API 测试。
