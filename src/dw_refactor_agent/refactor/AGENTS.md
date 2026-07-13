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
- `artifact_contract.py`：定义持久化 JSON 的 `format_version`、规范化摘要、原子写入和
  统一读取错误。
- `workspace_snapshot.py`：按文件路径和原始字节摘要当前项目资产、配置及相关工具源码，
  保护 analyze 后的 plan 不被工作区漂移静默复用。
- `semantic_mode.py`：解析 `equivalent` / `changed` / `unknown`、传播上游语义风险、
  复用同一语义上下文的用户声明并选择权威/观察性验证边界。
- `verification_plan.py`：推导 DDL 变化、最小作业重算集合、执行值、验证锚点与 checks。
- `plan_artifact.py`：将 baseline DDL 写为独立 SQL 文件，维护 plan 引用与 SHA-256
  校验，并在 shadow-run / compare 前物化可执行 plan。
- `shadow_scope.py`：表示并合并旁路读取、写入和预填充所需的行范围。
- `shadow_manifest.py`：运行时编译表路由、producer、作业依赖、prefill action、blocker 与 warning。
- `shadow_rewrite.py`：按编译后的路由上下文重写 SQL 表引用，生产读穿与 QA 读写规则以此处为准。
- `execution_provenance.py`：提供跨 worktree 的项目级本机互斥锁和 QA execution marker SQL。
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

# 后续阶段也可用精确 run id，系统不会猜“最新 run”
dw-refactor semantic-mode set --run <run_id> \
  --table <table> --mode equivalent|changed|unknown

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
都会更新 `current/`、`analysis/` 与 `verification/plan.json`。analyze 开始时先删除
旧 plan、shadow result 和 compare result；如果中途失败，不允许旧 plan 继续执行。

若 `jobs_to_run` 中包含配置了 `execution.slice` 或项目 `execution.default_slice`
的增量作业，必须通过 `--partition` 提供验证分区。planner 将其展开为作业的
`execution_values`；shadow-run 不使用当天日期或全局 driver value 兜底。仅当计划
不包含 sliced incremental 作业时才可省略 `--partition`。

`affected_scope` 是评估和验证推导使用的宽影响范围，不等于执行范围。
`jobs_to_run` 按语义边界选择并拓扑排序：直接变化的 `equivalent` 表只重算并比较
本表；`changed` / `unknown` 沿下游执行到最近的 `equivalent` 边界或观察性叶子。
未修改下游不会仅因为上游是 `equivalent` 就被重算。

语义判定优先级为：有效用户声明 > 上游 `changed` / `unknown` 传播 > 严格自动等价 >
默认 `unknown`。自动规则只接受 AST 相同的注释/格式变化和带稳定 `table_id` /
`column_id` 的可证纯重命名；普通 SQL diff 不自动判为等价。analyze 对 unknown 表中立
展示三种选择。用户设置后只轻量重建 plan，不要求填写原因。

轻量 replan 只复用当前 plan 绑定的 analysis inputs：baseline/current lineage、
change analysis、manifest 固定上下文和用户 semantic intent 都有独立 fingerprint。
任一输入或工作区变化都拒绝轻量 replan，要求重新 analyze。semantic intent 写入前会
使旧 verification 产物失效；即使 replan 失败，也不会留下可误执行的旧 plan。

用户声明保存在当前 run 的 `manifest.json.verification_intent.semantic_modes`，包含
`table_id`、mode、语义上下文 fingerprint 和确认时间。同一 table identity 与语义
上下文可从历史 run 复用；上下文变化时声明失效并产生 warning。声明随各 run 分散
保存，不维护会无限追加单条记录的项目级 decisions 文件；历史扫描会跳过损坏或版本
不符的 manifest，并一次构建声明索引供本次 analyze 使用。run 目录本身仍按审计历史
逐次增长；不需要保留时可按完整 run 目录归档或删除，不能只删其中的声明或基线文件。

### shadow-run

先用 `--dry-run` 检查编译后的路由、prefill、DDL 与作业调用。常用执行参数还包括：

- `--parallel`：全局 MySQL 并发度，默认 `1`。
- `--batch-size`：每个 MySQL session 执行的 slice invocation 数，默认 `1`。
- `--timing-detail` / `--profile`：在结果中记录 invocation 级耗时。

实际执行顺序为：

1. 编译 shadow manifest，发现 blocker 时停止。
2. Phase 0 重建 QA 库。
3. Phase 1 校验 `baseline_ddl_refs` 并用引用的 SQL 文件创建必要的基线表。
4. 按 manifest 的 `prefill_actions` 从生产库预填充自读、DDL-only 等必要数据。
5. Phase 2 应用 `ddl_changes`。
6. Phase 3 按 DAG 运行 `jobs_to_run`。

SQL 路由遵循“最小重算”：ODS、未变化的中间结果和无需 QA materialization 的关系
从生产库读取；已由本次计划重算且已 ready 的中间结果从 QA 库读取；作业输出统一
写入 QA 库。不要通过复制全部生产数据来绕过 manifest 路由和 prefill 计算。

shadow-run 在连接数据库前重新计算工作区 fingerprint，并校验 plan 本体、analysis
inputs 及所有外置 DDL。每次尝试先原子写入 `status=running` 和新的 execution ID；
成功执行后再把 execution ID、workspace/plan fingerprint 发布到 QA marker 表。
同一项目的本机进程（包括不同 worktree）共享互斥锁，避免同时改写 QA 库。dry-run、
running 或失败结果都不能作为 compare 凭据。

### compare

`compare` 消费 `verification.checks`，支持 `--method count|row_compare|all`、
`--sample` 和 `--precision`。`verification.compare_anchors` 提供时间列、粒度与锚点值；
缺少可用时间粒度时，planner 可能生成全表比较 warning。compare 还要求同目录的
`shadow_run_result.json` 来自 execute 模式、状态 completed，并与当前工作区和 plan 的
fingerprint 完全一致；校验在打开生产/QA 连接前完成。
compare 还会读取 QA marker，确认当前共享 QA 数据库确实来自该 execution ID；其他 run
重建过 QA 后，旧 shadow result 会被拒绝。

表/字段纯重命名时，count 分别读取 `prod_table` 与 `qa_table`；row compare 按稳定
`column_id` 构造两侧独立 projection。排除列按当前/QA 字段名解释，再映射到生产列。

`row_compare` 的排除列在 analyze 阶段从
`warehouses/{project}/warehouse.yaml` 的 `verification.row_compare` 写入最终 check：

- 项目级 `exclude_columns` 是默认值。
- `tables.<table>.exclude_columns` 覆盖项目级配置。
- 表级空列表表示全列比较。
- 计划未显式配置该字段时默认忽略 `etl_time`。

最终只使用 `verification_status`：`passed`、`passed_with_warnings`、`failed`、
`inconclusive`、`blocked`，不再写 `all_pass`。unknown 的匹配只能得到
`passed_with_warnings`；观察性 mismatch 或没有可执行锚点为 `inconclusive`。
CLI 对 passed 两态返回 0，failed/blocked 返回 1，inconclusive 返回 2。
只执行部分 method 或使用 `--sample` 时，即使已执行项全部匹配也只能得到
`inconclusive`；`compare_result.json.comparison` 会记录请求参数、必需/实际 checks
以及是否完整。

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
    ├── baseline_ddl/
    │   └── <table_name>.<ddl_sha256>.sql
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
- `verification_intent.semantic_modes`：用户或复用的表级语义声明；不是自动检测结果。

manifest 使用 `format_version=1` 并原子覆盖写入。当前设计不兼容缺少版本或版本不同的
旧产物；应新建 run，而不是迁移或猜测字段语义。

后续命令只要求传入 manifest，不应在调用方重新拼装产物路径。manifest 加载时会校验
必需字段、嵌套 semantic intent 类型，并拒绝绝对路径或逃逸 run 目录的 artifact 路径。
调整产物键或路径时，必须同步 `session.py`、所有消费者和相关测试；本模块不兼容旧
artifact schema。

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

- `baseline_ddl/*.sql`：由 `analyze` 生成，文件名同时包含表名和 DDL 内容 SHA-256。
  新 DDL 先原子写入，plan 原子发布成功后才清理旧 plan 不再引用的 `.sql`，从而保证
  任意时刻已发布 plan 的 refs 都可读取。
- `plan.json`：由 `analyze` 生成，是 shadow-run 与 compare 的共同输入。核心字段包括
  `changes`、`baseline_ddl_refs`、`ddl_changes`、`jobs_to_run` 与 `verification`。
  每个 baseline DDL 引用记录相对 `plan.json` 的 `path` 和文件字节的 `sha256`；
  shadow-run / compare 在继续前校验路径、文件存在性和摘要。内嵌 `baseline_ddl`
  的旧 plan 不再兼容，应重新运行 analyze（基线语义已变化时应新建 run）。
  `verification` 内含最终 `anchor_tables`、`compare_anchors`、checks、block status、
  warning、`target_semantics`、语义边界和必要的 metadata error。顶层
  `analysis_snapshot` 保存 partition、工作区 fingerprint，以及 baseline/current
  lineage、change analysis、manifest 固定上下文和 semantic intent 的 fingerprints；
  `plan_fingerprint` 覆盖除自身外的完整持久化 plan（DDL 内容由 refs 摘要绑定）。
- `shadow_run_result.json`：每次 shadow-run（包括 dry-run）覆盖写入，记录模式、状态、
  各 phase、作业/调用与可选耗时详情。运行时 shadow manifest 不单独落盘；其
  JSON 可序列化摘要嵌入本结果的 `shadow_manifest` 字段；结果还保存 execution ID、
  workspace 与 plan fingerprint。
- `compare_result.json`：每次 compare 原子覆盖写入，保存 `format_version`、
  `verification_status`、顶层 warnings、comparison 完整性、逐项 count / row_compare
  结果，以及绑定的 shadow execution/result fingerprint。没有合法数据锚点为
  inconclusive，硬 blocker 为 blocked。

manifest、plan、shadow result 和 compare result 均使用显式 `format_version=1`；写入
采用同目录临时文件、flush/fsync 后原子替换。版本错误、JSON 损坏、DDL 摘要不符、
analyze inputs 或工作区变化、semantic intent 与 plan 不一致、QA marker 或 shadow/plan
溯源不一致都必须 fail closed。

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
