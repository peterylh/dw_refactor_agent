# DDL 无本地 Task 时的冷启动模型生成改造方案

> 状态：Implemented（首版仅支持 `producer: external`）
> 基线分支：`codex/fix-cold-start-final-blockers`
> 基线提交：`3d9d116`
> 范围：`model_metadata_writer --mode generate` 的资产预检、执行契约、LLM 巡检与发布

本方案已按本文的 external producer 范围实现；`seed`、`manual`、`static` 等 producer
仍不在当前合同内。

## 1. 结论

建议不要把所有 `DDL -> 0 task` 直接静默放行，也不要为这类表伪造
`full + replace_all`。更稳妥的做法是：

1. 为合法的 DDL-only 表增加显式的项目级 `taskless` 声明；
2. 在正式 model 中增加一等的 `execution.mode: taskless` 状态；
3. taskless 表仍属于完整的 managed model set，照常生成、巡检和事务发布；
4. taskless 表不进入本地调度执行，执行器若发现真实 task 绑定到 taskless model，必须
   fail-closed；
5. 未声明的非 ODS DDL 仍然缺 task 时继续 blocked，避免误删 task 被静默掩盖；
6. generate 的 LLM 巡检集合改为以 immutable manifest 的
   `inspection_target_set` 为准，保证没有 lineage 的 DDL-only 表也能被巡检。

核心原则是把两个概念拆开：

- `managed=true`：该 DDL 必须有正式 model，属于冷启动完整发布集合；
- `execution.mode=taskless`：该表没有由本仓库 task SQL 驱动的本地作业。

DDL-only 表可以同时满足这两个条件，不应因为不可本地执行而失去模型元数据。

## 2. 当前问题

### 2.1 `task=0` 的真实含义

当前不是按 DDL 文件名和 task 文件名配对，而是解析 task SQL 的持久输出表，再按
`(catalog, database, table)` 的 canonical/casefold identity 绑定。

因此以下情况都会得到“主 task 为 0”：

- 项目中完全没有对应 task 文件；
- 有同名 task 文件，但 SQL 没有写入该 DDL 表；
- 只有 `tasks/full_refresh/` companion，没有普通主 task；
- task 输出 identity 与 DDL identity 不一致。

其中“完全没有任何 task”和“只有 full-refresh companion”必须分开处理：前者可以是合法
DDL-only，后者是孤儿 companion，仍应 hard block。

### 2.2 当前 blocked 链路

当前代码形成了两条互补的阻断分支：

| operational layer | 无主 task 时的推导 | blocked 来源 |
| --- | --- | --- |
| ODS | `full + replace_all` | 当前允许 |
| DIM | `full + replace_all` | manifest 直接增加 `execution_task_missing` |
| DWD/DWS | 不完整的 `incremental` | `_validate_execution()` 增加 `execution_task_missing` |
| ADS | `full + replace_all` | manifest 直接增加 `execution_task_missing` |

主要代码位置：

- [`generation_contract.py`](../../src/dw_refactor_agent/assessment/llm/generation_contract.py)
  的 `infer_execution_mapping()` 和 `_validate_execution()`；
- [`model_generation_manifest.py`](../../src/dw_refactor_agent/assessment/llm/model_generation_manifest.py)
  的 `build_generate_asset_preflight()`；
- [`model_metadata_writer.py`](../../src/dw_refactor_agent/assessment/llm/model_metadata_writer.py)
  的 `run_generate_model_metadata()`。

preflight 只要存在任何 error 就立即返回 blocked，后续不会创建 candidate、不会调用 LLM，
也不会进入事务发布。现有测试
[`test_model_metadata_writer_generation.py`](../../tests/assess/test_model_metadata_writer_generation.py)
中的 `test_run_generate_model_metadata_blocks_dwd_without_task_sql` 已把该行为固化为回归契约。

### 2.3 只删除 preflight 判断仍然不够

简单删除 `execution_task_missing` 会继续在后续阶段失败：

1. candidate validation 会再次调用 `_validate_execution()`；
2. effective candidate validation 还会再次验证 execution；
3. v3 model schema 当前强制要求 `materialized` 和
   `full_refresh_strategy`，不完整的 DWD/DWS fallback 无法通过 schema；
4. `execution_task_missing` 已注册为 deterministic hard-block issue；
5. taskless DDL 若没有 lineage，当前 `build_contexts()` 不会为它创建 LLM context。

所以这不是“把一个 error 改成 warning”就能解决的问题，需要补齐资产、模型、巡检和执行四个
边界的同一份合同。

### 2.4 隐藏的第二个失败点：inspection universe

[`context_builder.py`](../../src/dw_refactor_agent/assessment/llm/context_builder.py)
当前只遍历 `lineage_data["tables"]`。孤立 DDL-only 表通常没有 task，也就可能不在 lineage
snapshot 中。即使 preflight 放行，结果仍会是：

```text
manifest inspection_target_set 包含该表
  -> build_contexts 没有该表
  -> 没有 inspection report
  -> inspection_settled_set_incomplete
  -> not_published_inspection_failure
```

因此 manifest 的巡检目标必须真正传到 context builder，lineage 只能作为上下游和字段血缘
证据，不能决定 generate 的模型候选集合。

## 3. 目标与不变式

### 3.1 目标

- 合法 taskless DDL 可以生成完整 v3 model；
- 冷启动仍然发布完整 managed model set，不遗漏、不删除该表 model；
- 不伪造本地 materialization、slice 或 full-refresh 语义；
- taskless 表有 DDL、无 ETL 时仍可使用 DDL、注释和可用 lineage 做 LLM 巡检；
- task 增删发生在长时间 LLM 运行期间时，现有 manifest CAS 继续阻止过期候选发布；
- 执行器永远不会把 taskless model 当成可运行作业。

### 3.2 必须继续 hard block 的情况

- task 写入持久目标，但目标没有受管 DDL；
- task/DDL identity 冲突或无法稳定解析；
- 只有 full-refresh companion，没有主 task；
- 同一表同时存在 taskless 声明和真实主 task；
- taskless 声明使用短名、重复 identity、引用不存在的 DDL，或声明结构非法；
- 有主 task 时，materialization、slice、companion 等执行证据不闭合；
- asset manifest、catalog 或正式文件在运行期间发生变化；
- candidate set、model path、schema 或 publication invariant 不完整。

## 4. 新合同

### 4.1 项目级显式声明

在 `warehouse.yaml` 的 `execution` 下增加 taskless 资产声明。首版要求 fully-qualified
identity，不允许只写短表名。

```yaml
execution:
  schedule: scheduling/job_dag.json
  taskless_assets:
    - table: internal.demo_dm.dim_currency
      producer: external
      reason: maintained_by_upstream_sync
```

建议首版只接受 `producer: external`；如果后续确实需要区分 seed、manual、static，再扩展
枚举，不要在首版一次引入多个未经消费的状态。

规则：

- ODS 目录本身可作为“非 task_run 装载”的确定性证据，保持无需逐表声明；
- MID/ADS 的零 task DDL 必须存在显式声明；
- 声明只说明“不是本仓库 task producer”，不把该资产排除出 managed model set；
- 声明内容进入 project config hash 和每表 execution evidence hash；
- 声明变化会触发现有 publication CAS 的 `asset_manifest_changed`。

### 4.2 正式 model execution 合同

合法 taskless 表生成：

```yaml
version: 3
name: dim_currency
operational_layer: DIM
execution:
  mode: taskless
```

普通 task 表保持当前格式：

```yaml
execution:
  materialized: incremental
  full_refresh_strategy: replay_slices
  slice:
    param: etl_date
    column: stat_date
    period: D
```

兼容规则：

- `execution.mode` 缺省时按 `task` 处理，现有 v2/v3 task model 无需批量改写；
- `mode: taskless` 时禁止同时出现 `materialized`、`full_refresh_strategy`、`slice`；
- `mode: task` 或缺省模式继续使用现有 execution schema；
- taskless 是 operational state，不是 semantic section quarantine；
- `--require-complete` 不应因为 taskless 本身失败。

不建议生成下面这种占位合同：

```yaml
execution:
  materialized: full
  full_refresh_strategy: replace_all
```

它会虚构“本地 task 做全表替换”的语义。如果后续新增 task 但尚未重新 generate，旧 model
可能让执行器以错误策略运行；`mode: taskless` 则能在这个场景明确 fail-closed。

### 4.3 决策矩阵

| 主 task | full-refresh task | taskless 声明 | 结果 |
| --- | --- | --- | --- |
| 0 | 0 | ODS 隐式允许 | 生成 `mode: taskless` |
| 0 | 0 | 非 ODS 已声明 | 生成 `mode: taskless`，记录非阻断 diagnostic |
| 0 | 0 | 非 ODS 未声明 | `execution_task_missing` hard block |
| 0 | >0 | 任意 | 孤儿 companion hard block |
| >0 | 任意 | 无 | 按现有 SQL 证据推导 execution |
| >0 | 任意 | 有 | task/declaration conflict hard block |

## 5. 代码改造

### 5.1 统一解析 taskless policy

新增一个小型、无 I/O 副作用的 policy 解析模块，负责：

- 从已经加载的 project config 解析 `execution.taskless_assets`；
- canonicalize fully-qualified identity；
- 校验重复、短名、未知字段和 producer 枚举；
- 提供 `producer_mode_for(identity)`；
- 供 manifest、assessment 和执行边界复用，避免各处复制判断。

不要从旧 model YAML 推断 taskless；generate 冷启动仍然不能把旧 model 当作先验。

### 5.2 Manifest 与 preflight

修改
[`model_generation_manifest.py`](../../src/dw_refactor_agent/assessment/llm/model_generation_manifest.py)：

1. `ManagedGenerateAsset` 增加 `producer_mode` 和声明证据 hash；
2. `validation_asset()` 携带 `producer_mode`；
3. `table_tasks == []` 且 policy 允许时，execution contract 为
   `{"mode": "taskless"}`；
4. `main_tasks == []` 但 `table_tasks != []` 时继续 hard block，明确报告孤儿 companion；
5. 删除当前针对 DIM/ADS 的笼统“无 task 必 block”分支，改成 policy-aware 判断；
6. `GenerateAssetPreflight` 增加 warnings/diagnostics，`passed` 仍只取决于 errors；
7. manifest/result 输出 `taskless_table_count` 和 `taskless_tables`；
8. bump `MANIFEST_SCHEMA_VERSION`，使旧 checkpoint/cache 确定性失效。

`managed` 必须继续为 `true`，否则该表会从 expected model set 消失，违背冷启动完整发布合同。

### 5.3 Execution 推导与验证

修改
[`generation_contract.py`](../../src/dw_refactor_agent/assessment/llm/generation_contract.py)：

- 让 execution 推导同时读取 task evidence 和 `producer_mode`；
- taskless 直接返回 `{"mode": "taskless"}`，不再按 layer 猜
  `incremental/full`；
- `_validate_execution()` 使用同一决策矩阵；
- `taskless + task exists`、`task mode + task missing`、孤儿 companion 使用精确 error code；
- 保留有 task 时的 materialization、slice、partition overwrite 和 companion 校验。

建议保留 `execution_task_missing` 为 hard-block code，只收窄它的触发条件；另增加
`execution_task_binding_conflict` 和 `execution_main_task_missing`，并同步 typed issue registry。

### 5.4 Model schema 与候选渲染

修改以下位置：

- [`model_governance.py`](../../src/dw_refactor_agent/config/model_governance.py)：
  `_validate_execution_contract()` 接受 taskless 互斥结构；
- [`model_metadata_catalog.py`](../../src/dw_refactor_agent/assessment/llm/model_metadata_catalog.py)：
  `_catalog_model_payload()` 在 taskless 分支直接保留 execution，不能调用默认
  materialized 推导；
- [`model_metadata_updates.py`](../../src/dw_refactor_agent/assessment/llm/model_metadata_updates.py)：
  refresh/write 路径不得给 taskless model 自动补 `materialized`；
- [`generation_candidate_resolver.py`](../../src/dw_refactor_agent/assessment/llm/generation_candidate_resolver.py)：
  canonical v3 渲染必须保留 taskless operational contract，effective validation 使用相同
  task-binding 规则。

`MODEL_SCHEMA_V3` 可以保持不变，因为更新后的 reader 仍能读取缺少 mode 的旧 model，并按
task 解释。manifest schema 必须 bump，因为 manifest 的确定性输入语义已经变化。

这里是“新 reader 兼容旧 model”，不是“旧 reader 能读取新 taskless model”。如果生产环境
存在多版本进程滚动部署，应先发布能够读取 `mode: taskless` 的 reader/planner，再允许 writer
生成新合同；无法保证该顺序时，应升级为 model schema v4，而不是让旧进程误读或拒绝新文件。

### 5.5 LLM context 必须由 manifest target 驱动

把 `inspection_targets` 参数沿以下调用链传递：

```text
run_generate_model_metadata
  -> run_metadata_write
  -> run_inspection_pipeline
  -> build_contexts
```

修改
[`context_builder.py`](../../src/dw_refactor_agent/assessment/llm/context_builder.py)：

- `inspection_targets is not None` 时，精确遍历该 fully-qualified target set；
- `None` 表示沿用旧行为，空 tuple 表示明确的零目标，不能再 fallback 到 lineage；
- 不要与 lineage tables 做普通 union，否则额外 report 会被 outer transition 判为 unresolved；
- 把 target identities 加入 canonical dependency/model lookup 的 identity universe；
- target 与 lineage identity 按“fully-qualified 精确匹配 -> 唯一短名匹配”解析；无匹配按
  孤立资产处理，多匹配 hard block；
- `TableContext.table_identity` 使用 fully-qualified identity，`table_name` 保持唯一 model key；
- DDL 和空 ETL 从 frozen manifest `asset_content` 读取，优先使用 canonical identity 作为 key；
- lineage 只补充 upstream/downstream、depth 和 column lineage；
- 首次 API 调用前断言 context identity set 与 manifest target set 完全相等。

集合不一致应生成 typed `inspection_context_set_mismatch` deterministic hard block，不能被归类为
可恢复的服务故障或 semantic quarantine。writer 需要捕获对应领域异常并返回结构化 blocked
结果，不能让它退化为未处理异常或错误触发 inspection service breaker。

refresh 不传 `inspection_targets`，保持现有 lineage-driven 行为，避免扩大本轮改动范围。

### 5.6 执行、重构与评估边界

修改
[`execution/planner.py`](../../src/dw_refactor_agent/execution/planner.py)
和
[`execution/model_config.py`](../../src/dw_refactor_agent/execution/model_config.py)：

- planner 只为真实 task 创建 `TaskSpec`；
- 若真实 task 解析到 `mode: taskless` model，立即报错并提示移除声明、重新 generate；
- 禁止 taskless 合同走现有默认 `incremental` 分支；
- downstream 读取 external taskless 表时，把它视为 source anchor，由外部 producer 保证数据
  readiness，不创建虚假本地 producer job。

同时审计所有 `get_execution_contract()` 消费者。DDL-only 表没有 runnable job 时，应保持
“无作业”状态，不能默认成 incremental/full。现有 refactor 测试已经允许 DDL-only 表没有
lineage/job，新的 v3 taskless model 应保持该行为。

资产完整性规则
[`asset_completeness.py`](../../src/dw_refactor_agent/assessment/rules/definitions/asset_completeness.py)
也要复用同一 policy：

- 已声明 taskless 的表不再触发 `ASSET_EXECUTABLE_DDL_HAS_TASK`；
- 未声明的非 ODS 零 task 表仍然报告缺 task；
- 可新增一条 info/warning 检查，展示 taskless producer 和 reason。

实现完成时还要同步更新
[`assess_metadata_initialization.md`](../assess_metadata_initialization.md) 和
[`llm_cold_start_quarantine_plan.md`](llm_cold_start_quarantine_plan.md)，
把“所有 DWD/DWS 缺 task 都 blocked”收窄为“要求本地 task producer、但缺少主 task 时 blocked”。

## 6. 状态与诊断

合法 taskless 不是 error，也不是 quarantine：

- 无 LLM 的 MID 表仍按现有语义 section 规则发布为
  `published_with_quarantine`；
- 有 LLM 且语义完整时可以是 `published`；
- taskless diagnostic 不改变 candidate status 和 CLI 退出码；
- 结果 JSON 应明确列出 taskless tables、producer、reason 和声明来源；
- 未声明零 task、孤儿 companion 或 task/declaration conflict 仍返回 `blocked`、退出码 1。

不要把 taskless diagnostic 放进 `execution_*` hard-block issue registry；它应位于 preflight
warning/asset finding 中。只有合同冲突才生成 deterministic execution issue。

## 7. 测试矩阵

| 范围 | 场景 | 期望 |
| --- | --- | --- |
| Policy | fully-qualified 合法声明 | canonical identity 唯一解析 |
| Policy | 短名、重复、未知 producer、无对应 DDL | hard block |
| Manifest | ODS 无任何 task | pass，生成 taskless asset |
| Manifest | DWD/DWS/DIM/ADS 无 task且有声明 | pass，仍为 managed asset |
| Manifest | 非 ODS 无 task且无声明 | 保持 `execution_task_missing` |
| Manifest | 只有 full-refresh task | `execution_main_task_missing` |
| Manifest | 声明 taskless 后又出现主 task | binding conflict |
| Manifest CAS | LLM 运行中新增/删除 task 或修改声明 | `asset_manifest_changed` |
| Generate/no LLM | 合法 taskless MID | 完整 v3 model set，正式发布 |
| Generate/LLM | 无 lineage 的 taskless MID | 有且只有一个 context/report，ETL 为空 |
| Generate/LLM | task 与 taskless 混合项目 | inspection settled set 与 manifest 完全一致 |
| Context | 显式空 target set、lineage 仍有 MID 表 | contexts 保持为空，不 fallback |
| Context | FQ target 对应 short lineage 或存在短名歧义 | 唯一时保留血缘，歧义时 hard block |
| Checkpoint | taskless target 重跑或声明发生变化 | 可恢复 sidecar；manifest hash 变化后失效 |
| Candidate | taskless execution | schema/effective validation 通过 |
| Candidate | taskless 同时带 materialized/slice | hard block |
| Runtime | 完整 model 目录含 taskless 表但无对应 job | planner 正常 |
| Runtime | 新 task 绑定旧 taskless model | fail-closed |
| Assessment | 已声明 taskless | 不报 executable DDL 缺 task |
| Refactor | DDL-only 变更进入验证范围 | `jobs_to_run=[]`，DDL 仍参与验证 |
| CLI | 合法 taskless dry-run | 正确的 `would_publish_status`，零正式写入 |

需要反转或拆分现有测试：

- 保留“未声明 DWD 无 task 仍 blocked”；
- 新增“声明 taskless 后成功生成”；
- 不要直接把原 blocked 测试改成无条件放行。

建议验证命令：

```bash
make test PYTEST_ARGS='-q -m "not api" \
  tests/assess/test_generation_manifest.py \
  tests/assess/test_model_metadata_writer_generation.py \
  tests/assess/test_context_builder.py \
  tests/test_model_governance.py \
  tests/test_execution_planner.py \
  tests/refact/test_verification_plan.py'
```

## 8. 实施顺序

1. 定义并测试 taskless project policy 和 formal execution schema；
2. 改造 manifest/preflight，bump manifest schema；
3. 改造 execution inference、candidate validation 和 model 渲染；
4. 修复 generate inspection universe，覆盖无 lineage DDL；
5. 在 planner/refactor/assessment 边界增加 taskless 语义；
6. 补齐结果 diagnostics、CLI 文案和文档；
7. 跑定向测试，再跑完整 `make test`。

建议按上述顺序拆成 3 个提交：

1. `feat(config): define taskless execution contract`
2. `fix(assessment): generate models for declared taskless ddl assets`
3. `test(assessment): cover taskless cold-start boundaries`

## 9. 验收标准

- 一个只有 MID DDL、无 task、无 lineage，但存在合法 taskless 声明的项目，可以完成
  generate；
- candidate model 数量与受管 DDL 数量完全一致；
- 正式 taskless model 不包含伪造的 materialized/strategy/slice；
- `--llm` 对每个 manifest inspection target 恰好生成一个 settled report；
- taskless 表不会出现在 schedule 或 `jobs_to_run`；
- 新增真实 task 后，旧 taskless model 在执行边界 fail-closed；
- 未声明的非 ODS 零 task 表、孤儿 companion、task target 缺 DDL 等错误仍然 blocked；
- 运行期间 task/config 变化仍被 publication CAS 拒绝；
- 现有 task-backed 项目的生成结果和执行行为不发生语义回归。

## 10. 不采用的方案

### 10.1 所有零 task 自动放行

无法区分合法外部生产和误删 task，会把确定性资产错误静默合法化。

### 10.2 为零 task 统一填 `full + replace_all`

execution 语义不真实，并可能在后续新增 task、尚未重新 generate 时诱发错误执行策略。

### 10.3 把 DDL-only 表排除出 managed model set

会造成正式 model 集不完整，甚至在 replace-existing 发布时删除旧 model。

### 10.4 把 execution 问题做成 semantic quarantine

execution 是 operational contract，不属于 classification/business semantics/entities/grain/
metrics 中任何一个可隔离 section。把它塞进语义 quarantine 会混淆治理边界。

### 10.5 只修改 preflight

candidate/effective schema validation 和 inspection settled set 仍会失败，不能真正完成冷启动。
