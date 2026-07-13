# 语义感知的重构 Compare 目标设计

## 背景与问题

当前重构验证将直接变化表的一跳下游选为 Compare 锚点。只要存在下游锚点，直接修改的任务表就不会进入 `count` / `row_compare`。这会让下游未消费字段、被聚合抵消的差异和直接表自身的粒度变化漏过验证。

另一方面，不能把所有直接修改表无条件加入 Compare。部分重构会有意改变中间表语义，此时要求该表与生产基线相等没有意义，应当在语义保持稳定的下游边界验证。

系统需要区分以下三种语义模式，并将用户意图、自动判断和上游语义传播纳入最终 Compare 计划：

- `equivalent`：预期基线与当前输出语义等价；权威比较本表，并在此停止向未修改下游传播。
- `changed`：预期本表输出语义变化；不要求本表与基线相等，继续在下游寻找验证边界。
- `unknown`：系统和用户都未确认；继续做可用的下游观察性比较，但必须显著提示风险。

本设计对应 Issue #67，但修复目标不是“所有直接变化表都无条件 Compare”，而是按语义模式生成验证目标。

## 目标

1. 语义等价的直接修改任务必须进入直接 Compare。
2. equivalent 表完成完整权威比较后成为传播停止边界，不无条件重算未修改下游。
3. 语义有意变化的表不做错误的等值断言，而是在下游验证声明的不变量。
4. 无法判断时不阻断默认流程，继续验证下游并返回 warning。
5. 用户声明优先，不强制填写原因。
6. 自动判断只接受能够严格证明的有限等价场景，不让普通 SQL diff 或 LLM 猜测成为等价证明。
7. 上游语义变化必须沿受影响 DAG 传播，避免把“本表 SQL 未变”误当成“本表输出等价”。
8. 用户对完全相同的语义上下文只确认一次，可跨 run 复用；资产或上游语义上下文改变后自动失效。
9. 提供短 `--run` CLI，避免重复输入完整 manifest 路径。
10. 用户确认后只轻量重建 plan；仅当 analyze 后工作区发生变化时要求完整重跑 analyze。
11. Semantic-mode set、shadow-run 和 compare 都拒绝消费与当前工作区不一致的陈旧 plan；compare 还必须确认 QA 结果来自同一份 plan。

## 非目标

- 不实现通用 SQL 语义等价证明器。
- 不由 LLM 自动决定 `equivalent` 或 `changed`。
- 不在 model YAML 中长期保存某张表的固定语义模式。
- 不默认选择“最新 run”。
- 不改变现有最小作业重算和生产/QA 路由原则。

## 术语与字段

### 用户声明：`declared_mode`

`declared_mode` 只来自用户，可为 `equivalent`、`changed`、`unknown`，未声明时为 `null`。用户声明不要求 reason。

### 自动判断：`automatic_mode`

`automatic_mode` 只来自严格、确定性的规则。第一版只输出 `equivalent` 或 `null`，绝不自动输出 `changed`。

### 最终结果：`resolved_mode`

`resolved_mode` 是 planner 结合用户声明、上游语义传播、自动判断和默认策略得到的最终模式。`resolved_source` 记录来源：

- `user`
- `inherited_user`
- `upstream_propagation`
- `automatic`
- `default_unknown`

示例：

```json
{
  "declared_mode": null,
  "automatic_mode": "equivalent",
  "resolved_mode": "unknown",
  "resolved_source": "upstream_propagation",
  "upstream_context": [
    {
      "table": "dwd_order_detail",
      "resolved_mode": "changed"
    }
  ]
}
```

本表任务未变只能支持 `automatic_mode=equivalent`；上游为 `changed` 时，输出仍必须降为 `resolved_mode=unknown`。

## 判定优先级

按受影响作业 DAG 的拓扑顺序解析每张物化表：

```text
有效的 declared_mode
    >
changed / unknown 上游传播
    >
automatic_mode=equivalent
    >
default unknown
```

详细规则：

1. 有有效用户声明时，`resolved_mode=declared_mode`，`resolved_source=user`。用户声明 `equivalent` 可以在上游变化后主动建立新的语义边界。
2. 没有用户声明，且任一受影响上游的 `resolved_mode` 为 `changed` 或 `unknown`，本表解析为 `unknown`，来源为 `upstream_propagation`。
3. 没有上述上游风险，且严格规则得到 `automatic_mode=equivalent`，本表解析为 `equivalent`。
4. 其他情况解析为 `unknown`。
5. `changed` 只允许用户声明，不由结构、元数据差异或 LLM 自动推断。

自读增量任务的自身边不作为独立上游语义源；其任务、DDL 和 model 已包含在本表本地变更指纹中。

## 自动等价规则

第一版坚持小而可证，仅支持：

1. 本表相关资产完全未变，且所有受影响上游均为 `equivalent`。
2. 任务差异仅为注释、空白或格式变化，规范化 SQL AST 相同。
3. 受管表/字段纯重命名：
   - `table_id` / `column_id` 保持；
   - DDL 除重命名外没有字段增删、类型、nullable、default、key、partition 或其他结构变化；
   - model 除名称引用外，grain、指标、业务过程和 execution 配置不变；
   - 应用 rename mapping 后，基线与当前任务 SQL 的规范化 AST 相同；
   - 字段级输出表达式除标识符映射外一致。

以下变化第一版一律不自动证明等价：

- 普通过滤条件或日期边界改写；
- JOIN 类型或条件变化；
- 聚合、去重、窗口或 NULL 处理变化；
- 删除临时表或 CTE；
- `SELECT *` 展开为显式字段；
- 指标表达式、grain、业务过程或字段结构变化。

这些变化可以在未来增加独立、经过测试的严格规则；未覆盖时均为 `automatic_mode=null`。

## 上游语义传播与验证边界

对于每个 `changed` 或 `unknown` 表，planner 沿下游遍历：

1. 遇到 `resolved_mode=equivalent` 的最近物化后代时，将其作为权威语义边界并停止该路径继续传播。
2. 遇到 `changed` 时继续向下游传播。
3. 遇到 `unknown` 时继续向下游传播并记录风险链路。
4. 如果直到叶子都没有 `equivalent` 边界，则把结构可比较的叶子作为观察性锚点；没有可比较叶子时只保留 warning。

对于直接修改且 `resolved_mode=equivalent` 的表：

- 本表加入权威 Compare；
- 本表成为该路径的语义传播停止边界；
- task、DDL、model 均未修改且不涉及 rename 引用传播的下游，不进入 `jobs_to_run` 或 anchors；
- 下游自身发生变化时，作为独立直接变化表按自己的 `resolved_mode` 决定是否执行和比较；
- 用户显式要求额外验证的下游可以加入，但不属于默认最小验证范围。

Equivalent 声明只有在本表能够执行完整 required Compare 时才能建立停止边界。若 schema mapping、时间锚点或其他比较元数据不完整，验证应 blocked，不能静默跳过本表后改用下游证明 equivalent。

## 语义感知的作业选择

`affected_scope` 继续保留直接变化表和完整下游影响范围，供评估、解释和 fingerprint 使用，但不再等同于执行范围。

```text
jobs_to_run = 所有可执行的直接变化任务
            union changed/unknown 到选定下游边界之间的任务路径
            union 用户显式要求的额外验证任务
```

以下关系不单独选择下游作业：

```text
直接变化 equivalent 表
    -> 未修改下游任务
```

以下关系仍选择下游作业：

- 上游为 `changed` 或 `unknown`，需要沿路径计算下游验证边界；
- 下游 task、DDL 或 model 自身发生变化；
- 表/字段 rename 导致下游任务引用发生变化；
- 用户显式要求额外下游验证。

因此，语义解析在 job selection 之前完成；执行值传播只作用于最终 `jobs_to_run`。未选择的下游继续按现有最小路由从生产读取，不创建 QA 输出。

## 表和字段重命名的直接 Compare

当前 Compare 假设生产表与 QA 表同名、字段同名。纯重命名的等价表需要扩展 check：

```json
{
  "table": "DIM_BASE_STORE_PROFILE_INFO",
  "prod_table": "dwd_store",
  "qa_table": "DIM_BASE_STORE_PROFILE_INFO",
  "method": "row_compare",
  "column_mapping": [
    {
      "column_id": "89316282-1115-42d8-b953-5c41134e7829",
      "prod": "store_name",
      "qa": "STORE_NAME"
    }
  ]
}
```

`count` 分别读取 `prod_table` 与 `qa_table`。`row_compare` 按稳定 `column_id` 生成两侧显式 projection，并统一排序和结果位置；排除列配置按当前/QA 逻辑表名解析，再映射到生产列。

如果用户声明 `equivalent`，但 schema identity 无法构造完整的一一映射，planner 保留声明但将验证标记为 blocked；不能只比较公共列后宣称等价。

## Fingerprint

### 本地变化指纹

`local_change_fingerprint` 绑定本表基线与当前的语义相关资产：

```text
SHA256(canonical_json({
  fingerprint_version,
  project,
  table_id,
  baseline: {
    logical_name,
    ddl_path + content_sha256,
    task_path + content_sha256,
    full_refresh_task_path + content_sha256,
    model_path + content_sha256
  },
  current: {同上}
}))
```

规则：

- 使用原始文件字节的 SHA-256，不使用 mtime。
- JSON key 和资产列表稳定排序。
- 缺少资产显式记录为 `null`。
- `table_id` 关联重命名前后的表。
- `base_commit` 只作为审计字段，不进入 digest；相同资产对可跨 run 复用。

### 语义上下文指纹

`semantic_context_fingerprint` 将上游语义纳入声明有效性：

```text
SHA256(canonical_json({
  fingerprint_version,
  local_change_fingerprint,
  affected_upstreams: sorted([
    upstream_table_id,
    upstream_semantic_context_fingerprint,
    upstream_resolved_mode
  ])
}))
```

用户声明绑定 `semantic_context_fingerprint`。只要本表资产、受影响祖先资产或祖先最终模式改变，旧声明即 stale；无关链路变化不会使声明失效。

## 持久化模型

### Run manifest

Manifest 保存本次 run 的用户输入，不保存自动推导结果：

```json
{
  "format_version": 1,
  "verification_intent": {
    "semantic_modes": {
      "dws_store_sales_daily": {
        "mode": "equivalent",
        "semantic_context_fingerprint": "sha256:...",
        "confirmed_at": "2026-07-13T15:30:00+08:00"
      }
    }
  }
}
```

Analyze 必须保留已有 `verification_intent`。声明 fingerprint 不匹配时不删除旧值，而是在 plan 中标记 stale 并按未声明处理，便于审计和重新确认。

Manifest 不保存 `last_analyze`。Analyze 的输入快照属于派生 plan 的生成上下文，不属于用户意图。

### 历史 run 决策复用

不新增独立、无限增长的项目 decision cache。跨 run 复用直接读取已有 run manifests，它们已经是用户决策的审计来源。

Analyze 按时间从新到旧读取同项目的历史 manifests，并在拓扑解析每张表时查找：

- 相同 `table_id`；
- 相同 `semantic_context_fingerprint`；
- 合法的三态 mode。

第一个精确匹配的历史声明复制进当前 manifest，并记录 `inherited_from_run_id`；plan 使用 `resolved_source=inherited_user`。用户选择的 `unknown` 也可复用，表示该风险已被用户接受而无需重复询问。

历史声明优先级低于当前 run 声明，高于自动判断。删除历史 run 会失去对应复用能力，但不会影响正确性；下次同类变更回到 unknown 并重新确认。

持久化写入要求：

- 保留 manifest 中其他表的声明；
- 使用同目录临时文件加原子 replace 写入当前 manifest；
- manifest 无法解析时阻断写入；
- 损坏或格式版本不匹配的历史 manifest 跳过复用并输出 CLI 诊断，不污染本次 verification warning；
- 当前 manifest 损坏或版本不匹配时直接阻断。

## Plan 输出

Plan 保存本次 analyze 的输入快照，用于保护轻量 replan：

```json
{
  "format_version": 1,
  "plan_fingerprint": "sha256:...",
  "analysis_snapshot": {
    "partition": "2024-12-31",
    "workspace_fingerprint": "sha256:..."
  }
}
```

`analysis_snapshot.workspace_fingerprint` 覆盖 change analysis 使用的全部变化资产和配置。`semantic-mode set` 重新计算当前值；不一致时拒绝轻量 replan并要求完整 analyze。此前系统没有这一检查：analyze 每次从 baseline Git commit 重新计算 changed files，但 analyze 完成后的 shadow-run/compare 不会重新检查工作区。

Fingerprint 输入包含所有可能影响本项目 plan 或 shadow 执行的源码文件：项目 DDL、task、full-refresh task、model、warehouse/config/业务语义文件、全局命名配置，以及 refactor/lineage/DDL derivation/execution/config/SQL rewrite 相关工具源码。生成 artifacts、文档、测试和无关项目文件不参与，避免无关变化使 plan 失效。新增、删除和重命名的相关文件都进入规范化 `{path, content_sha256}` 列表。

`verification.target_semantics` 保存每张受影响物化表的完整解析结果：

```json
{
  "dws_store_sales_daily": {
    "declared_mode": null,
    "automatic_mode": null,
    "resolved_mode": "unknown",
    "resolved_source": "upstream_propagation",
    "local_change_fingerprint": "sha256:...",
    "semantic_context_fingerprint": "sha256:...",
    "upstream_context": [
      {
        "table": "dwd_order_detail",
        "resolved_mode": "changed"
      }
    ],
    "evidence": []
  }
}
```

`verification.target_semantics` 只保存结构化语义事实，不内嵌 warning。所有风险提示集中在 `verification.warnings`，由 compare 复制到最终结果并统一展示。

`verification.checks` 不增加 `authority`。Compare 通过 check 对应表在 `target_semantics` 中的 `resolved_mode` 判断语义：

- `equivalent`：该表检查是等值断言，mismatch 导致 `failed`；
- `unknown`：该表检查是观察性比较，match 仍保留 warning，mismatch 得到 `inconclusive`；
- `changed`：不生成该表的直接检查。

所有 check 必须能关联一个 `target_semantics` 条目；planner 在持久化前验证这一不变量，避免 checks 与语义来源重复存储后发生漂移。

## Plan 新鲜度与执行溯源

写入 plan 时同时计算并保存顶层 `plan_fingerprint`。其规范化输入为：移除顶层 `plan_fingerprint` 后的完整 plan JSON，以及按路径排序的所有外置 baseline DDL `{path, content_sha256}`；JSON 使用稳定 key 顺序和固定编码后计算 SHA-256。这样 fingerprint 覆盖持久化 plan 与引用内容，同时避免字段自引用。所有后续阶段执行前都必须验证：

1. 当前相关工作区文件重新计算出的 fingerprint 与 `analysis_snapshot.workspace_fingerprint` 一致；
2. 当前 plan 内容及 baseline DDL refs 与 `plan_fingerprint` 一致。

不一致时阶段以 `stale_plan` 阻断，并要求重新 analyze；不能继续执行或仅给 warning。

实际 shadow-run 完成后，`shadow_run_result.json` 保存：

```json
{
  "format_version": 1,
  "mode": "execute",
  "status": "completed",
  "workspace_fingerprint": "sha256:...",
  "plan_fingerprint": "sha256:..."
}
```

Dry-run 结果不能作为 compare 的执行凭据。Compare 除验证当前工作区和 plan 外，还必须读取 shadow-run result，要求：

- `mode=execute` 且 `status=completed`；
- shadow result 的 workspace fingerprint 等于 plan analysis snapshot；
- shadow result 的 plan fingerprint 等于当前 plan。

因此：

- analyze 后修改工作区，semantic-mode set 和 shadow-run 都会拒绝；
- shadow-run 后修改工作区，compare 会拒绝；
- shadow-run 后重新生成或修改 plan，compare 会拒绝并要求重新 shadow-run；
- semantic-mode set 轻量 replan 会生成新的 plan fingerprint，之前的 shadow result 自动失效；
- 重新 analyze 后必须重新执行 shadow-run，旧 QA 执行结果不能复用。

该机制解决本地工作区和 plan 漂移，不负责冻结外部生产数据库。生产锚点数据在 shadow-run 与 compare 之间被其他流程修改，仍属于独立的数据快照一致性问题。

## 验证状态与 warning

Compare 结果只使用 `verification_status`，不再保留 `all_pass`：

- `passed`：所有 equivalent checks 通过，且没有 unknown 风险。
- `passed_with_warnings`：所有 equivalent 和 unknown 观察性 checks 均匹配，但存在 unknown 链路或 stale 声明等风险。
- `failed`：任一 equivalent check 不匹配。
- `inconclusive`：没有可执行锚点，或只有 observational checks 且出现 mismatch；结果不足以确认或否定声明的业务正确性。
- `blocked`：声明 equivalent 但无法构造完整比较、时间元数据错误或其他硬阻塞。

Compare result 使用 `format_version=1`，持久化 `verification_status`、顶层 `warnings` 和逐项 `results`。CLI 退出码为：`passed` / `passed_with_warnings` 返回 0，`failed` / `blocked` 返回 1，`inconclusive` 返回 2。

Unknown 示例 warning：

```json
{
  "type": "unknown_table_semantics",
  "table": "dws_store_sales_daily",
  "message": "Only downstream observational anchors are compared; passing checks does not prove this table is equivalent."
}
```

CLI 和结果摘要显示总体 `verification_status`，并在 `passed_with_warnings` / `inconclusive` 时集中显示 `verification.warnings` 的表和原因。`target_semantics` 不重复保存 warning。

## 用户交互

Unknown 不提供倾向性建议。Agent 或交互层中立展示三种选择：

```text
dws_store_sales_daily 无法自动确认语义。

- equivalent：预期新旧输出相同；比较本表，未修改下游不重算
- changed：预期本表语义变化；只验证下游
- unknown：暂不判断；验证下游并保留风险 warning
```

非交互 CLI 不询问，直接保留 unknown、生成下游 observational checks 和 warning。

## CLI

在 `pyproject.toml` 注册：

```toml
[project.scripts]
dw-refactor = "dw_refactor_agent.refactor.run:main"
```

所有消费 manifest 的命令接受互斥参数：

- `--manifest <path>`：精确路径，适用于 CI 和非标准位置。
- `--run <run_id>`：在所有配置项目的标准 refactor run 目录中唯一解析。

不允许隐式 latest。零匹配或多匹配时列出可操作错误并要求使用精确 manifest。

设置语义模式：

```bash
dw-refactor semantic-mode set \
  --run 20260713_113226_shop \
  --table dws_store_sales_daily \
  --mode equivalent
```

命令执行：

1. 读取当前 plan 和 manifest。
2. 重算 `analysis_snapshot.workspace_fingerprint`；不一致则拒绝并提示重跑 analyze。
3. 获取该表当前 `semantic_context_fingerprint`。
4. 原子更新当前 manifest。
5. 基于已有 `change_analysis.json`、`current/lineage_data.json`、baseline commit 和 `analysis_snapshot.partition` 轻量重建 `verification/plan.json` 及外置 baseline DDL 引用。
6. 不刷新 lineage、assessment 或 issue diff。

`analyze`、`shadow-run`、`compare` 同样支持 `--run`：

```bash
dw-refactor analyze --run 20260713_113226_shop --partition 2024-12-31
dw-refactor shadow-run --run 20260713_113226_shop
dw-refactor compare --run 20260713_113226_shop --method all
```

`shadow-run` 在重建 QA 前执行 workspace/plan freshness 检查。`compare` 在建立数据库连接前执行 workspace/plan freshness 和 shadow execution provenance 检查；任何一项失败都不得读写数据库。

## 产物格式

- Manifest 和 plan 都使用新的必填 `format_version=1`；这是第一版显式版本化产物格式。
- 不实现旧 manifest、旧 plan 或旧 compare result 的兼容分支。
- `start` 只创建新格式；所有 producer 和 consumer 在同一变更中切换到新格式。
- 格式版本不匹配时直接报错并要求新建 run，不做字段猜测或隐式迁移。

## 错误处理

1. 非法 mode、未知表或不属于受影响范围的表：拒绝写入。
2. Manifest declaration fingerprint stale：按未声明处理并 warning，不静默复用。
3. Replan 前 workspace fingerprint 变化：拒绝轻量 replan，提示完整 analyze。
4. Shadow-run / compare 前 workspace 或 plan fingerprint 变化：以 `stale_plan` 阻断，不访问数据库。
5. Compare 缺少同 plan 的已完成 execute shadow result：以 `stale_shadow_result` 阻断。
6. 用户声明 equivalent 但无法建立完整 schema/column mapping：blocked。
7. 受影响图无法拓扑排序：沿用现有 DAG blocker，不生成不可信语义结果。
8. 无 equivalent 下游边界：尽可能生成 observational leaf checks；checks 全部匹配时为 `passed_with_warnings`，没有 checks 或 observational mismatch 时为 `inconclusive`，不能给出确定性 passed。
9. 历史 manifest 损坏或版本不匹配：跳过继承并输出 CLI 诊断；当前 manifest 出现相同问题时阻断。

## 测试策略

### 单元测试

- 三态输入解析和非法值。
- declared / upstream / automatic / default 的优先级。
- `changed` 与 `unknown` 的多层下游传播和最近 equivalent 边界选择。
- equivalent 直接表停止传播，未修改下游不进入 jobs 或 anchors。
- 下游自身变化或 rename 引用传播时，即使上游 equivalent 也独立进入 jobs。
- 未修改下游因 changed 上游降为 unknown。
- 用户 equivalent 在 changed 上游后建立边界。
- 纯注释/格式和稳定 ID 纯 rename 自动 equivalent。
- 普通 filter/JOIN/aggregate/SELECT-star 改写保持 automatic null。
- local/context fingerprint 稳定性、无关变更不失效、祖先变化必失效。
- 当前 run 声明和历史 run 声明的优先级与复用。
- stale 声明、损坏历史 manifest、当前 manifest 原子写入与其他表声明保留。
- `--run` 唯一解析、零/多匹配和与 `--manifest` 互斥。
- semantic-mode set 的 workspace stale 拒绝和轻量 replan。
- analyze 后修改 task/DDL/model/config/tool source 时，shadow-run 在任何数据库写入前以 stale plan 拒绝。
- shadow-run 后修改工作区或 plan 时，compare 在连接数据库前拒绝。
- compare 拒绝 dry-run、失败执行或 plan fingerprint 不匹配的 shadow result。
- rename table/column 的 prod/QA projection mapping。
- 根据 target semantics 汇总 passed / passed_with_warnings / failed / inconclusive / blocked。
- format version 不匹配时明确拒绝，不存在旧格式兼容分支。

### 全量测试

按项目要求执行：

```bash
make doctor
make test
```

不直接运行裸 pytest。

## Shop 真实场景验收

在 shop 项目完成一次真实 Doris shadow-run/compare 验收，至少覆盖：

1. 对 `dws_store_sales_daily.sql` 制造一个无法由第一版严格规则证明的等价 SQL 改写。
2. `start` / `analyze --partition 2024-12-31` 后，该表解析为 unknown；DWS 不直接 Compare，下游 checks 为 observational，结果带 warning。
3. 使用 `semantic-mode set --mode equivalent` 确认后不重跑 lineage/assessment，仅轻量 replan。
4. 新 plan 包含 `dws_store_sales_daily` 的 required count/row_compare，并从 `jobs_to_run` 和 anchors 移除未修改的 `ads_store_performance`、`dim_store_metric_snapshot`。
5. 再对一个下游任务制造独立变化，确认该下游按自己的 resolved mode 重新进入 jobs 和 checks。
6. 实际 shadow-run 和 compare 通过；结果为 `verification_status=passed`。
7. 再创建相同资产差异的新 run，从历史 manifest 自动复用用户确认。
8. 再修改一次 DWS SQL，fingerprint 改变，旧确认失效并重新变成 unknown warning。
9. Analyze 后再次修改 DWS SQL，确认 shadow-run 在重建 QA 前以 stale plan 拒绝。
10. 重新 analyze 和 shadow-run 后再次修改工作区，确认 compare 在连接数据库前拒绝。
11. 恢复工作区并重新完成 analyze/shadow-run/compare，确认 plan/shadow fingerprints 一致且验证通过。
12. 验收完成后恢复临时 shop 资产，不把场景改动提交到功能分支。

同时使用纯表/字段重命名测试确认稳定 identity 能自动得到 equivalent，并能直接比较生产旧名与 QA 新名。

## 持久化文件详细 Review 清单

实现完成后的代码 Review 必须重点检查：

1. Manifest 更新不会丢失现有 artifacts、base_git、root 或未知扩展字段。
2. Analyze 不覆盖有效用户声明；stale 声明可审计但不生效。
3. 历史 manifest 复用只接受相同 table identity、context fingerprint 和合法 mode，不引入额外永久 cache 文件。
4. Fingerprint 不包含 mtime、run_id 或 base commit 字符串，且包含所有声明所需的祖先语义上下文。
5. `analysis_snapshot` 位于 plan 而非 manifest，轻量 replan 在 workspace 变化时必定拒绝，不消费陈旧 analysis/lineage。
6. Workspace fingerprint 覆盖所有 plan/shadow 相关项目资产与工具源码，不包含 artifacts、docs、tests 和无关项目。
7. Plan fingerprint 覆盖持久化 plan 和 baseline DDL refs；shadow result 准确绑定 workspace 和 plan fingerprints。
8. Shadow-run / compare freshness 检查发生在任何数据库连接、重建或查询之前。
9. Plan、baseline DDL refs、shadow-run、compare 的 format version 和持久化 schema 同步。
10. Checks 不重复存储 authority，Compare 只依据 target semantics 解释等值断言和观察性结果。
11. Warnings 只在 verification/result 顶层保存，target semantics 不保存重复 warning。
12. 损坏或部分写入的当前 manifest 不会被静默覆盖。
13. 临时 shop 验收资产完全恢复，Git diff 只包含预期功能、测试和文档。

## 验收标准

1. 直接修改的 equivalent 表生成 required checks，并阻止未修改下游进入 jobs 和 anchors。
2. changed 表不生成直接等值检查，并在最近 equivalent 下游边界验证。
3. 下游自身变化、rename 引用传播或用户显式选择时，独立进入执行和比较范围。
4. unknown 不阻断默认流程，但最终结果明确为 warning，Agent 可请求用户三选一。
5. 上游 changed/unknown 正确使未声明下游降为 unknown。
6. 用户声明无需 reason，且只在 context fingerprint 有效时生效。
7. 相同语义上下文从历史 run manifests 复用确认，任何相关祖先或本地变化使确认失效。
8. `--run` 和 `dw-refactor` 短入口可用，精确 `--manifest` 入口可用。
9. 用户确认后只轻量 replan，工作区变化时安全拒绝。
10. Shadow-run 和 compare 都拒绝陈旧 workspace/plan，compare 只消费同 plan 的已完成 execute shadow result。
11. 聚焦测试、完整非 API 测试和 shop 真实 shadow-run/compare 验收全部通过。
12. 新格式不包含旧产物兼容分支，持久化文件详细 Review 无未解决的高、中优先级问题。
