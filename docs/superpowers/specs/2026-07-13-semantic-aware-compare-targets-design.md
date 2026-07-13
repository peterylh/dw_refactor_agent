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
- `cached_user`
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
  "verification_intent": {
    "semantic_modes": {
      "dws_store_sales_daily": {
        "mode": "equivalent",
        "semantic_context_fingerprint": "sha256:...",
        "confirmed_at": "2026-07-13T15:30:00+08:00"
      }
    }
  },
  "last_analyze": {
    "partition": "2024-12-31",
    "workspace_fingerprint": "sha256:..."
  }
}
```

Analyze 必须保留已有 `verification_intent`。声明 fingerprint 不匹配时不删除旧值，而是在 plan 中标记 stale 并按未声明处理，便于审计和重新确认。

`last_analyze.workspace_fingerprint` 覆盖本次 change analysis 使用的全部变化资产和配置。轻量 replan 前重新计算；不一致时拒绝并要求完整 analyze，避免使用陈旧的 lineage/change analysis。

### 项目决策缓存

完全相同的语义上下文可跨 run 复用：

```text
warehouses/{project}/artifacts/refactor_semantic_decisions.json
```

```json
{
  "version": 1,
  "decisions": {
    "sha256:...": {
      "table_id": "c888836b-b989-4845-998f-882c362cca3f",
      "mode": "equivalent",
      "confirmed_at": "2026-07-13T15:30:00+08:00"
    }
  }
}
```

该文件是本地生成产物，加入 `.gitignore`，不作为项目长期治理配置。Manifest 仍记录每个 run 实际采用的用户声明以供审计。

缓存优先级低于当前 run 声明，高于自动判断。命中缓存时，planner 将决策复制进当前 manifest，并在 plan 中记录 `resolved_source=cached_user`。缓存中的 `unknown` 也可复用，表示用户已经选择保留风险而无需反复询问。

持久化写入要求：

- 保留未知 manifest keys 和其他表的声明；
- 使用同目录临时文件加原子 replace 写入 manifest 与 decision cache；
- decision cache 按 fingerprint 去重、稳定排序；
- manifest 无法解析时阻断写入；
- cache 缺失视为空；cache 损坏时 analyze 忽略缓存、产生 warning，`semantic-mode set` 拒绝覆盖并提示人工处理。

## Plan 输出

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
    "evidence": [],
    "warnings": ["upstream_semantics_changed"]
  }
}
```

`verification.checks` 增加 `authority`：

- `required`：等价声明或等价边界的权威检查；不匹配使验证失败。
- `observational`：unknown 链路上的观察性检查；匹配也不能证明语义等价。

## 验证状态与 warning

保持 `all_pass` 作为“所有已执行 checks 是否匹配”的兼容字段，同时增加 `verification_status`：

- `passed`：所有 required checks 通过，且没有未覆盖 unknown 风险。
- `passed_with_warnings`：checks 均匹配，但存在 observational checks、unknown 链路、stale 声明或损坏缓存等风险。
- `failed`：任一 required check 不匹配；observational mismatch 也记录，但不伪装为权威语义失败。
- `inconclusive`：没有可执行锚点，或只有 observational checks 且出现 mismatch；结果不足以确认或否定声明的业务正确性。
- `blocked`：声明 equivalent 但无法构造完整比较、时间元数据错误或其他硬阻塞。

Unknown 示例 warning：

```json
{
  "type": "unknown_table_semantics",
  "table": "dws_store_sales_daily",
  "message": "Only downstream observational anchors are compared; passing checks does not prove this table is equivalent."
}
```

CLI 和结果摘要必须显示 unknown 表、传播来源、检查 authority 和总体 `verification_status`，不能只展示 `all_pass=true`。

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

- `--manifest <path>`：精确路径，保留兼容性，适用于 CI 和非标准位置。
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
2. 重算 `last_analyze.workspace_fingerprint`；不一致则拒绝并提示重跑 analyze。
3. 获取该表当前 `semantic_context_fingerprint`。
4. 原子更新 manifest 和项目 decision cache。
5. 基于已有 `change_analysis.json`、`current/lineage_data.json`、baseline commit 和 `last_analyze.partition` 轻量重建 `verification/plan.json` 及外置 baseline DDL 引用。
6. 不刷新 lineage、assessment 或 issue diff。

`analyze`、`shadow-run`、`compare` 同样支持 `--run`：

```bash
dw-refactor analyze --run 20260713_113226_shop --partition 2024-12-31
dw-refactor shadow-run --run 20260713_113226_shop
dw-refactor compare --run 20260713_113226_shop --method all
```

## 兼容性

- `--manifest` 保持可用。
- 旧 manifest 缺少新字段时按无声明处理。
- 旧 plan 不包含 `target_semantics` / `authority`，shadow-run 和 compare 应要求重新 analyze；不对语义选择做隐式兼容猜测。
- `all_pass` 保留，但新消费者应优先读取 `verification_status`。
- 新 plan schema、外置 baseline DDL 和所有消费者必须同步更新。

## 错误处理

1. 非法 mode、未知表或不属于受影响范围的表：拒绝写入。
2. Manifest declaration fingerprint stale：按未声明处理并 warning，不静默复用。
3. Replan 前 workspace fingerprint 变化：拒绝轻量 replan，提示完整 analyze。
4. 用户声明 equivalent 但无法建立完整 schema/column mapping：blocked。
5. 受影响图无法拓扑排序：沿用现有 DAG blocker，不生成不可信语义结果。
6. 无 equivalent 下游边界：尽可能生成 observational leaf checks；checks 全部匹配时为 `passed_with_warnings`，没有 checks 或 observational mismatch 时为 `inconclusive`，不能给出确定性 passed。
7. Decision cache 损坏：analyze 忽略并 warning；set 命令不覆盖损坏文件。

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
- 当前 run 声明和跨 run decision cache 的优先级与复用。
- stale 声明、损坏缓存、原子写入与未知 key 保留。
- `--run` 唯一解析、零/多匹配和与 `--manifest` 互斥。
- semantic-mode set 的 workspace stale 拒绝和轻量 replan。
- rename table/column 的 prod/QA projection mapping。
- required 与 observational check 的 pass/fail/status 汇总。
- 旧 manifest 和旧 plan 的明确兼容策略。

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
7. 再创建相同资产差异的新 run，decision cache 自动复用用户确认。
8. 再修改一次 DWS SQL，fingerprint 改变，旧确认失效并重新变成 unknown warning。
9. 验收完成后恢复临时 shop 资产，不把场景改动提交到功能分支。

同时使用纯表/字段重命名测试确认稳定 identity 能自动得到 equivalent，并能直接比较生产旧名与 QA 新名。

## 持久化文件详细 Review 清单

实现完成后的代码 Review 必须重点检查：

1. Manifest 更新不会丢失现有 artifacts、base_git、root 或未知扩展字段。
2. Analyze 不覆盖有效用户声明；stale 声明可审计但不生效。
3. Decision cache 文件路径、gitignore、版本、稳定排序、去重与原子替换正确。
4. Fingerprint 不包含 mtime、run_id 或 base commit 字符串，且包含所有声明所需的祖先语义上下文。
5. 轻量 replan 在 workspace 变化时必定拒绝，不消费陈旧 analysis/lineage。
6. Plan、baseline DDL refs、shadow-run、compare 的持久化 schema 同步。
7. `all_pass` 与 `verification_status` 不产生“unknown 也完全通过”的误导。
8. 损坏或部分写入文件不会被静默覆盖。
9. 临时 shop 验收资产完全恢复，Git diff 只包含预期功能、测试和文档。

## 验收标准

1. 直接修改的 equivalent 表生成 required checks，并阻止未修改下游进入 jobs 和 anchors。
2. changed 表不生成直接等值检查，并在最近 equivalent 下游边界验证。
3. 下游自身变化、rename 引用传播或用户显式选择时，独立进入执行和比较范围。
4. unknown 不阻断默认流程，但最终结果明确为 warning，Agent 可请求用户三选一。
5. 上游 changed/unknown 正确使未声明下游降为 unknown。
6. 用户声明无需 reason，且只在 context fingerprint 有效时生效。
7. 相同语义上下文跨 run 复用确认，任何相关祖先或本地变化使确认失效。
8. `--run` 和 `dw-refactor` 短入口可用，旧 `--manifest` 保持可用。
9. 用户确认后只轻量 replan，工作区变化时安全拒绝。
10. 聚焦测试、完整非 API 测试和 shop 真实 shadow-run/compare 验收全部通过。
11. 持久化文件详细 Review 无未解决的高、中优先级问题。
