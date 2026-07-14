# Shadow-run QA 数据库池设计

## 背景

当前项目的 verification plan 从 `warehouse.yaml.qa_database` 读取一个固定 QA
数据库。每次实际 shadow-run 都先以 QA 用户执行：

```sql
DROP DATABASE IF EXISTS <qa_database>;
CREATE DATABASE <qa_database>;
```

不同 refactor run 因此会重建同一个数据库。项目级本机文件锁只能串行化同一台机器上
的进程，不能支持多台开发机或多个 CI runner 并发；compare marker 只能发现数据库
已被替换，不能阻止干扰。

生产 Doris 中的 `qa` 用户目前只对精确数据库 `internal.shop_dm_qa` 拥有库级
`Select_priv`、`Load_priv`、`Alter_priv`、`Create_priv`、`Drop_priv` 和
`Show_view_priv`，没有创建任意动态数据库的全局或 catalog 权限。因此运行时按
run/execution 动态创建数据库需要扩大权限，不采用该方案。

## 目标

- 允许不同 refactor run 在不同机器上并发执行 shadow-run 和 compare。
- 不授予 QA 用户创建任意数据库的权限。
- 由 DBA 预建固定数据库池，shadow-run 原子领取一个空闲池槽。
- shadow-run 和 compare 完成后保留 QA 数据，由人工 `dw-refactor cleanup` 释放。
- cleanup 可以列出池槽，按 run ID、execution ID 或创建时间选择并清理。
- 数据库领取、compare 和 cleanup 均校验 ownership，错误时 fail closed。
- 保留现有 workspace、plan、execution marker fingerprint 绑定语义。

## 非目标

- 不引入常驻 agent、TTL janitor、心跳或租约。
- 不自动判断一个已领取池槽中的进程是否仍存活。
- 不自动清理 shadow-run 或 compare 的成功、失败结果。
- 不支持同一个 refactor run 并发写同一组本地产物；同一 run 的命令仍需串行。
- 不为生产数据库提供任何写路径；生产数据只作为 shadow-run 和 compare 的读取源。

## 核心概念

- **run ID**：`start` 创建的逻辑重构验证会话，绑定 baseline、analyze、plan 和语义
  声明。
- **execution ID**：一次实际 shadow-run 尝试。一个 run 可因重试产生多个 execution。
- **pool slot**：DBA 预建并授权给 QA 用户的固定数据库。
- **claim marker**：池槽内的保留表，用于原子领取和持久化不可变 ownership。

run 与 execution 保持一对多关系。每个 execution 独占一个池槽，直到人工 cleanup；
同一 run 的重试不会覆盖前一次 execution 的 QA 数据。

## 项目配置

在 `warehouse.yaml.verification` 中增加显式数据库池：

```yaml
qa_database: shop_dm_qa
verification:
  qa_database_pool:
    - shop_dm_qa
    - shop_dm_qa_02
```

约束如下：

- `qa_database` 保留，作为兼容配置和默认 dry-run 路由名。
- `verification.qa_database_pool` 存在时必须是非空、去重后的数据库名列表。
- 每个池槽必须使用合法 Doris identifier，且不能等于生产库、lineage 库或系统库。
- 未配置池时回退为单元素 `[qa_database]`，以保持其他项目可加载；该单槽仍使用新的
  claim/cleanup 协议，不再由 shadow-run 无条件 DROP/CREATE。
- verification plan 持久化 run ID 和规范化后的 `qa_database_pool`，plan fingerprint
  覆盖这两个字段。
- 池配置变化使旧 plan 的 workspace/plan fingerprint 失效，必须重新 analyze。

Shop 首次上线配置为 `shop_dm_qa` 和 `shop_dm_qa_02`。`shop_dm_qa_02` 由 root 在
生产 Doris 中一次性创建，并授予与当前 `shop_dm_qa` 相同的 QA 库级权限。

## 池槽状态与兼容识别

本设计不维护 shadow-run 生命周期状态。cleanup 只识别池槽的可用性：

- `free`：没有 claim marker，且没有其他表。
- `claimed`：存在新版 marker，且 marker schema、单行 ownership 和数据库名校验通过。
- `legacy`：存在当前旧版 execution marker；不会被新 allocator 或按时间 cleanup 使用。
- `invalid`：marker 缺行、损坏、版本不符，或无 marker 但数据库非空。

这些值是池槽检查结果，不是 `running/completed/failed` 执行状态。系统无法判断
`claimed` execution 是否仍在运行；操作者执行 cleanup 时负责确认时机。

当前生产 `shop_dm_qa` 已确认包含旧版 `dw_refactor_execution_marker`、
`dws_store_sales_daily` 和 `stage_store_sales_daily`，首次上线后应显示为 `legacy`，
不得自动覆盖。新增的空 `shop_dm_qa_02` 用于首次真实验证。旧槽只有经过显式 legacy
清理后才可回到 `free`。

## Claim marker

继续使用保留表名：

```text
dw_refactor_execution_marker
```

新版 marker 包含一个 ownership 记录：

```text
format_version
marker_key
project
run_id
execution_id
qa_database
plan_fingerprint
workspace_fingerprint
claimed_at
```

字段均不可变，不增加 status、finished_at、heartbeat 或 lease。`claimed_at` 使用
Doris `NOW()`，避免跨机器本地时钟差异。表 schema 和 marker `format_version`
用于区分新版、旧版和损坏的 marker。

marker 必须在任何 baseline DDL、prefill、DDL change 或 job SQL 之前创建。项目资产
不得定义、读取、写入、重命名或删除该保留表；shadow manifest 编译时发现引用必须
产生 blocker。

## 原子领取协议

每次实际 shadow-run 在 plan/workspace 新鲜度校验通过后生成 execution ID，并按
execution ID 对池列表做确定性轮转，避免所有进程总是竞争第一个槽。对候选槽执行：

1. 只读检查槽是否为 `free`。
2. 不带 `IF NOT EXISTS` 创建 claim marker 表。
3. 多个执行者竞争同一槽时，只有一个 `CREATE TABLE` 成功；失败者重新检查槽并继续
   尝试下一个候选。
4. 成功者插入 ownership 行并立即回读，确认 run、execution、数据库名和 fingerprints。
5. 插入或回读失败时保留 marker 表，使槽表现为 `invalid`，并停止执行；不得在失败
   路径删除可能已经被其他进程观察到的 claim。
6. 所有槽均非 free 时，命令 fail closed，打印每个槽的 availability、owner 和 age，
   不覆盖任何现有数据。

数据库和 marker 表的 DDL 是跨机器共享的 Doris 元数据边界，不依赖本机 `flock`。
本地锁缩小到单个 run 的 artifact 写入范围，不再阻塞不同 run 使用不同池槽。

## Shadow-run 数据流

### Dry-run

`shadow-run --dry-run` 不领取池槽、不创建 marker、不写 Doris。它使用 plan 中的默认
QA 名称编译和展示 SQL 路由，同时明确输出“实际池槽将在 execute 模式领取”和候选池
列表。dry-run result 不包含可供 compare 使用的 ownership。

### Execute

实际执行顺序调整为：

1. 校验 fresh plan bundle、workspace 和 plan fingerprints。
2. 使用 plan 默认 QA 名称预编译 shadow manifest，只用于发现与物理池槽无关的
   blocker；发现 blocker 时停止，此时尚未领取池槽。
3. 生成 execution ID，原子领取 pool slot。
4. 用领取到的数据库覆盖运行时 plan 副本的 `qa_db`；不修改已持久化 plan。
5. 用运行时 plan 副本重新编译 shadow manifest。所有实际 rewrite、prefill 和 job
   执行只消费这份绑定真实池槽的 runtime manifest；若重新编译意外失败，保留已领取
   槽并 fail closed。
6. 校验槽内只有新版 marker，然后创建 baseline 表、prefill、应用 DDL changes 并执行
   jobs。
7. 将实际 `qa_db`、execution ID、run ID 和 fingerprints 原子写入
   `shadow_run_result.json`。
8. 无论成功或失败都保留池槽和 marker，等待 cleanup。

不再执行 Phase 0 的 `DROP DATABASE` / `CREATE DATABASE`。Phase 0 改为
`claim_qa_slot`，结果记录候选池、领取结果和实际数据库。

若进程在领取后被强杀，marker 仍保留，池槽保持 claimed/invalid；这是预期的
fail-closed 行为。

## Compare 数据流

compare 不再把 persisted plan 的默认 `qa_db` 当作物理数据库。它必须：

1. 校验 fresh plan 和合法 execute-mode `shadow_run_result.json`。
2. 从 shadow result 读取实际 `qa_db` 和 execution ID。
3. 确认实际数据库属于 plan 的 `qa_database_pool`。
4. 回读实际数据库 marker，确认 project、run ID、execution ID、数据库名、plan 和
   workspace fingerprints 全部一致。
5. 以实际数据库执行现有 count/row_compare checks。
6. compare result 继续绑定 shadow execution/result fingerprint。

marker 不匹配、池配置不包含实际数据库或槽已被 cleanup 时，compare 在读取生产/QA
数据前拒绝执行。

## Cleanup CLI

统一入口增加 `cleanup list` 和 `cleanup delete`：

```bash
dw-refactor cleanup list
dw-refactor cleanup list --project shop
dw-refactor cleanup list --run <run_id>

dw-refactor cleanup delete --execution <execution_id> --yes
dw-refactor cleanup delete --run <run_id> --yes
dw-refactor cleanup delete --project shop --older-than 7d --yes
dw-refactor cleanup delete --project shop \
  --created-before 2026-07-01T00:00:00+08:00 --yes
dw-refactor cleanup delete --project shop --database shop_dm_qa --yes
```

### List

- 只扫描已加载项目配置中的 pool slot，不扫描或推断任意数据库。
- 每个槽显示 project、database、availability；claimed 槽额外显示 run ID、execution
  ID、claimed_at 和 age。
- `--project` 和 `--run` 是只读筛选。
- legacy/invalid 槽显示诊断信息，不伪造 run ID。

### Delete

- 普通 claimed 清理至少要求 `--execution`、`--run`、`--older-than` 或
  `--created-before` 之一。
- 多个选择器按 AND 组合。
- 按时间批量清理必须指定 `--project`；跨项目必须显式 `--all-projects`。
- 时间条件只匹配新版 claimed marker 的 `claimed_at`，不自动匹配 legacy/invalid。
- 不带 `--yes` 时只打印计划，不执行写操作。
- 执行前重新读取并校验 marker，避免 list 与 delete 之间 ownership 发生变化。
- 清理时先删除 views 和普通业务表，再删除 marker 表；marker 必须最后删除。
- 部分清理失败时保留 marker，继续处理其他目标，最终汇总 released、blocked 和 failed；
  有 blocked/failed 时返回非零。
- 删除 marker 成功后数据库本身仍存在并成为 free slot。

legacy/invalid 槽不进入普通 ID 或时间删除。它们只能通过精确 `--database` 预览并配合
`--yes` 清理；数据库必须是项目配置中的 pool member。精确数据库清理仍不得操作
生产库、lineage 库或未配置数据库。

由于没有状态或租约，cleanup 可能清理一个仍被执行进程使用的 claimed 槽。该风险由
显式选择器、预览和 `--yes` 控制，属于用户已接受的简化取舍。

## 产物与兼容性

- verification plan 增加 manifest `run_id` 和规范化后的 `qa_database_pool`。
- `shadow_run_result.json.qa_db` 记录实际领取的 pool slot，而非配置默认值。
- execution ID 保持每次实际 shadow-run 生成 UUID 的现有语义。
- top-level shadow/compare result 仍代表该 run 最近一次命令；历史 retained execution
  通过 pool marker 被 cleanup 发现，不新增 execution artifact 目录。
- 旧 plan 缺少 pool 字段时以 `[qa_db]` 解析，但工作区变更仍会使已发布旧 plan stale；
  不允许绕过重新 analyze 执行。
- 旧 marker 只读识别为 legacy，不原地迁移或覆盖。

## 模块边界

新增 `src/dw_refactor_agent/refactor/qa_pool.py`，负责：

- pool 配置解析与校验；
- identifier 安全校验和 SQL quoting；
- 槽检查、marker schema/ownership 读取；
- 原子领取；
- cleanup 选择、预览和释放。

现有模块调整：

- `verification_plan.py`：持久化规范化 pool。
- `plan_artifact.py`：校验 pool schema。
- `execution_provenance.py`：保留 execution/result fingerprint 契约；项目级锁改为 run 级
  artifact 锁，marker SQL 由 `qa_pool.py` 管理。
- `shadow_run.py`：先编译、再领取，使用运行时 QA 数据库，不再 DROP/CREATE 数据库。
- `compare.py`：从 shadow result 解析实际数据库并验证 pool marker。
- `run.py`：增加 cleanup 子命令并保持 CLI 编排薄层。
- `config/core.py`：校验 verification pool 配置。
- 根 `AGENTS.md`、refactor `AGENTS.md`：同步 pool、cleanup 和并发语义。

## 错误处理

- 无 free slot：失败并列出占用，不回退到共享 QA 数据库。
- marker 创建竞争失败：重新检查并尝试下一个槽，不把普通 DDL 错误误判为竞争。
- marker 插入/回读失败：槽标记为 invalid，停止 shadow-run。
- shadow-run SQL 失败：保留 claimed 槽和结果，供排查和 cleanup。
- compare marker 不匹配：连接生产库前失败。
- cleanup marker 不匹配：阻止该槽，继续其他槽。
- cleanup 删除部分对象失败：不删除 marker，保持槽不可领取。

## 自动化测试

遵循 TDD，至少覆盖：

- 配置 pool 的加载、默认回退、去重和危险数据库拒绝。
- verification plan/persisted plan 的 pool 字段与 fingerprint。
- 两个并发 allocator 竞争同一槽只有一个成功，失败者领取下一槽。
- 所有槽占用时 fail closed。
- legacy、invalid、free、claimed 槽识别。
- dry-run 不领取、不写库。
- execute 先编译 blocker，再领取实际槽，且不执行 DROP/CREATE DATABASE。
- 领取后使用实际槽重新编译 runtime manifest，实际执行不复用 preview 路由。
- 运行时 SQL rewrite、prefill、DDL 和 job 全部使用实际槽。
- shadow result 保存实际槽和 ownership。
- compare 使用 shadow result 实际槽，并拒绝非 pool/marker mismatch。
- 不同 run 的锁不互相阻塞，同一 run 的 artifact 写入保持串行。
- cleanup list 的 project/run 筛选和输出。
- cleanup delete 的 execution/run/time 选择器、AND 语义、preview/`--yes`。
- cleanup 删除 marker 最后执行；中途失败保留 marker。
- legacy/invalid 只能通过精确数据库名清理，且必须是已配置 pool member。
- 表名大小写按现有 canonical 规则处理，用户可见名称保留展示大小写。

focused tests 通过后运行项目规定的完整非 API 测试，不直接运行裸 `pytest`。

## 生产配置与真实验证

实现和自动化测试通过后执行以下受控步骤：

1. 使用 root 只读确认 `shop_dm_qa_02` 不存在。
2. 使用 root 创建一个空的 `shop_dm_qa_02`。
3. 为 `qa` 授予与 `shop_dm_qa` 相同的库级权限，并用 `SHOW GRANTS` 验证。
4. 将 Shop pool 配置为 `[shop_dm_qa, shop_dm_qa_02]`。
5. 执行 `cleanup list --project shop`，确认旧 `shop_dm_qa` 为 legacy，新库为 free。
6. 创建一个新的 Shop refactor run，analyze 后先执行 dry-run，确认没有领取槽。
7. 执行真实 shadow-run，确认领取 `shop_dm_qa_02`、不修改/重建生产库，并写入新版
   marker。
8. 执行 compare，确认它使用 shadow result 中的实际槽并通过 marker provenance 校验；
   无数据锚点时允许按现有语义返回 inconclusive。
9. 执行 cleanup preview，再以 execution ID 和 `--yes` 释放测试槽，确认数据库仍存在且
   重新显示为 free。

真实验证只允许写预建 QA pool slot。任何命令输出出现生产数据库写 SQL、权限超出预期
或 ownership 不一致时立即停止。

## Code Review 与完成条件

实现、自动化测试和真实验证完成后执行独立 Code Review，重点检查：

- pool claim 的跨进程竞争和 TOCTOU 边界；
- SQL identifier quoting 与误删生产/非 pool 数据库风险；
- marker fail-closed 行为；
- compare provenance 是否仍绑定 exact execution；
- cleanup 是否确实最后删除 marker；
- 旧 plan/marker 兼容是否明确；
- 不同 run 并发与同一 run artifact 串行边界；
- 文档、CLI help 和测试是否同步。

Review 发现的问题必须修复并重新验证。完成标准为：focused tests、完整非 API 测试、
prod QA pool 真实验证和 Code Review 均通过，且生产数据库未发生写入。
