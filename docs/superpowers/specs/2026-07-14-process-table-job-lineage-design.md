# Process Table and Cross-job Lineage Design

日期：2026-07-14

## 背景

当前血缘抽取以表名识别过程表，并在资产图中全局折叠同名过程表。不同 Job 各自创建和
使用同名过程表时，来自多个 Job 的上游与下游会被交叉组合，产生不存在的字段血缘、
表血缘和执行依赖。

生产环境还存在另一种合法场景：Job A 使用普通 `CREATE TABLE` 或 CTAS 生成持久化
过程表，Job A 结束后该表仍然存在，Job B 再读取它。此时不能简单地把所有过程表都限制
在单个 Job 内，否则会丢失真实的跨 Job 血缘。

本设计在不引入 `logical_process_id` 的前提下，同时解决同名局部过程表隔离和唯一共享
过程表的跨 Job 血缘。

## 目标

1. 不同 Job 使用同名局部过程表时，不产生交叉血缘。
2. 普通持久化过程表存在唯一生产者时，生成正确的跨 Job 表级、字段级和执行血缘。
3. 将 Job 提升为 `lineage_data.json` 的一等实体，每条 SQL 血缘边显式归属一个 Job。
4. Job DAG 直接由 Job 的数据输入输出和已解析的数据依赖生成，不要求任务名等于输出
   表名。
5. 对零生产者和多生产者给出结构化诊断，不依据文件顺序猜测生产者。
6. 保持旧版 lineage JSON 和 Job DAG 可读，新生成产物使用版本 2。

## 非目标

- 不引入过程表的跨运行逻辑 ID。
- 不关联两次运行中已经改名的过程表。
- 不根据 SQL 文件顺序、文件名排序或抽取顺序选择“最后一个生产者”。
- 不接入外部调度平台的运行实例、完成时间或人工优先级。
- 不支持 `CREATE TEMPORARY TABLE` 跨数据库 Session 传播血缘。
- 不自动修改业务 SQL，也不强制业务立即治理现有过程表。

## 术语

### 正式受管表

存在项目受管 DDL 或模型元数据的 ODS、DWD、DWS、DIM、ADS 等表。它们即使位于加工
链路中间，也仍然是正式数据集。

### 普通过程表

由任务 SQL 使用普通 `CREATE TABLE`、CTAS 或写入语句维护，服务于加工链路且不是正式
受管资产的物理表。它可能只在一个 Job 中使用，也可能在 Job 结束后保留并被其他 Job
读取。

### 数据库临时表

由 `CREATE TEMPORARY TABLE` 创建、生命周期受数据库 Session 约束的表。它不能作为
其他 Job 的合法生产者。

### 局部与共享

“局部”或“共享”不是表的持久属性，而是针对某个消费者解析生产者时得到的关系状态：

- 消费者 Job 内存在自己的生产者时，使用 `(job, canonical_fqn)` 作为局部匹配键。
- 消费者 Job 内没有生产者，且其他 Job 中恰好有一个合法持久化生产者时，解析为共享。
- 零个或多个外部生产者都不形成跨 Job 血缘。

因此公开 JSON 不增加 `lineage_scope`，也不持久化 `scope_job`。复合局部键只存在于解析
器和图构建过程内部。

## 方案选择

评估过三种方案：

1. 所有过程表都限制在 Job 内：不会串血缘，但丢失生产中的共享过程表依赖。
2. 所有同名表都全局合并：容易生成跨 Job 血缘，但保留当前交叉污染问题。
3. Job 内生产者优先，唯一外部生产者才跨 Job：同时满足隔离与共享要求。

采用第三种方案。

## Lineage JSON v2

### 顶层结构

```json
{
  "format_version": 2,
  "tables": [],
  "jobs": [],
  "edges": [],
  "diagnostics": []
}
```

### Table

删除新产物中的 `is_transient`、`transient_sources` 和拟议中的
`is_process_table`、`lineage_scope`。使用一个描述性枚举：

```json
{
  "name": "t",
  "full_name": "internal.shop_dm.t",
  "dataset_type": "process",
  "columns": []
}
```

`dataset_type` 的取值为：

- `managed`：项目正式受管表。
- `process`：任务 SQL 创建或维护的普通过程表。
- `temporary`：只以数据库临时表形式出现的数据集。
- `external`：被任务读取但不由当前项目管理或生产的数据集。

该字段用于描述和展示，不作为跨 Job 匹配的唯一依据。跨 Job 资格由每个 Job 的语句事实
决定，避免同一物理名称在不同 Job 中用途不同时再次被全局类型污染。

类型判定优先级为：

1. 出现在受管 DDL/模型中时为 `managed`。
2. 被普通 `CREATE TABLE`、CTAS 或其他持久化写入维护时为 `process`。
3. 仅以 `CREATE TEMPORARY TABLE` 出现时为 `temporary`。
4. 只有读取事实时为 `external`。

### Job

```json
{
  "name": "prepare_sales",
  "source_file": "mid/tasks/prepare_sales.sql",
  "inputs": [
    "internal.shop_dm.ods_order"
  ],
  "outputs": [
    "internal.shop_dm.t"
  ]
}
```

约束：

- `name` 在单个项目快照内唯一。
- `source_file` 只保存在 Job 上，作为 SQL 定位和审计信息。
- `inputs` 记录该 Job 读取的数据集。
- `outputs` 记录普通持久化写入；`CREATE TEMPORARY TABLE` 和在同一 Job 中创建后删除的
  表不作为跨 Job 输出候选。
- 所有标识符比较使用统一 canonical/casefold key，展示值保留现有大小写。

### Edge

所有由一条任务 SQL 直接抽取的字段转换和条件依赖都归属于一个 Job：

```json
{
  "source": {
    "type": "column",
    "id": "internal.shop_dm.ods_order.amount"
  },
  "target": {
    "type": "column",
    "id": "internal.shop_dm.t.amount"
  },
  "relation_type": "direct",
  "transformation_type": "direct",
  "expression": "amount",
  "job": "prepare_sales"
}
```

版本 2 的 Edge 不保存 `source_file`。需要定位 SQL 时，通过 `edge.job` 连接
`jobs[].name`，再读取 `jobs[].source_file`。

`edges` 只保存可以归属到单个任务 SQL 的事实，不把跨 Job 传递闭包伪装成属于某一个
Job 的直接边。跨 Job 字段血缘由查询和资产图基于多条直接边组合得到。例如：

```text
ods_order.amount --prepare_sales--> t.amount
t.amount         --build_report-->  ads_report.sales_amount
```

旧版顶层 `indirect_edges` 只作为读取兼容输入。版本 2 生成器不新增跨 Job `job_path`
产物；现有 JOIN、WHERE、GROUP BY 等条件依赖仍作为单 Job Edge 保存，并引用该 Job。

### Diagnostics

生产者解析失败不会中止整个快照，也不会生成猜测依赖：

```json
{
  "code": "UNRESOLVED_DATASET_PRODUCER",
  "dataset": "internal.shop_dm.t",
  "reason": "multiple_candidates",
  "consumer_jobs": ["build_report"],
  "candidate_producer_jobs": [
    "prepare_sales_a",
    "prepare_sales_b"
  ]
}
```

`reason` 支持：

- `not_found`：没有合法生产者。
- `multiple_candidates`：存在多个合法外部生产者。

诊断引用 Job，不重复保存 `source_file`；展示层可以通过 Job 查到文件路径。

## 任务级 SQL 事实

每个任务在抽取时需要形成以下事实：

- `input_tables`：所有被读取的表。
- `output_tables`：所有普通持久化写入的表。
- `created_tables`：普通或临时 CREATE 事实及语句位置。
- `dropped_tables`：DROP 事实及语句位置。
- `temporary_tables`：由 `CREATE TEMPORARY TABLE` 创建的表。
- `local_lifecycle_tables`：在同一任务内创建后删除、不能跨 Job 使用的表。

普通 `DROP TABLE IF EXISTS t; CREATE TABLE t AS ...` 且创建后没有再次 DROP，表示最终
表仍然存在。它必须保留为持久化输出候选，不能因为名称包含 `tmp` 或存在前置 DROP 就
自动判定为局部临时表。

任务缓存继续可以使用 `source_file` 作为内部缓存键；删除 `source_file` 只针对版本 2
的公开 Edge 契约。

## 生产者解析

针对消费者 Job C 读取的数据集 T，按以下顺序解析：

1. 查找 C 自身对 T 的创建或写入事实。
2. 如果存在自身生产者，T 在 C 的相关路径中按 `(C, T)` 隔离，不生成 Job 自依赖，也
   不与其他 Job 的同名局部路径组合。
3. 如果不存在自身生产者，查找其他 Job 的合法持久化输出。
4. 排除 `CREATE TEMPORARY TABLE` 和在生产 Job 内已经删除的输出。
5. 恰好一个候选时，生成跨 Job 数据依赖，并允许字段路径跨越 T。
6. 零个候选时输出 `not_found`；多个候选时输出 `multiple_candidates`。

生产者选择不使用任务扫描顺序、文件名顺序、JSON 顺序或 SQL 中最后一个 CREATE 的
静态位置。完整 catalog、database/schema 和 table 名参与匹配；所有匹配大小写不敏感。

## 同名过程表隔离

假设两个任务分别包含：

```text
job_a: src_a -> t -> out_a
job_b: src_b -> t -> out_b
```

由于每个消费者都能在本 Job 找到 T 的生产者，解析器使用两个内部节点：

```text
(job_a, canonical(t))
(job_b, canonical(t))
```

只允许生成：

```text
src_a -> out_a
src_b -> out_b
```

禁止生成：

```text
src_a -> out_b
src_b -> out_a
```

## 唯一共享过程表

假设：

```text
prepare_sales.outputs = {internal.shop_dm.t}
build_report.inputs   = {internal.shop_dm.t}
```

`build_report` 内没有 T 的生产者，且 `prepare_sales` 是唯一合法外部生产者，则建立：

```text
prepare_sales --internal.shop_dm.t--> build_report
```

字段图保留两段直接边，并在查询时组合跨 Job 路径。共享过程表作为路径证据保留，不通过
不透明的 `relation_type=process_table` 表示。

## Job DAG v2

Job DAG 是从 lineage 快照派生的执行视图，不是核心血缘事实来源：

```json
{
  "format_version": 2,
  "jobs": [
    "prepare_sales",
    "build_report"
  ],
  "data_dependencies": [
    {
      "upstream_job": "prepare_sales",
      "downstream_job": "build_report",
      "datasets": [
        "internal.shop_dm.t"
      ]
    }
  ],
  "deps": {
    "prepare_sales": ["build_report"],
    "build_report": []
  },
  "rev": {
    "prepare_sales": [],
    "build_report": ["prepare_sales"]
  }
}
```

- `jobs` 保存全部执行节点，包括孤立 Job。
- `data_dependencies` 保存依赖双方和形成依赖的数据集证据。
- `deps` 是正向邻接表，供拓扑排序和执行使用。
- `rev` 是反向邻接表，供入度计算和上游查询使用。
- 同一对 Job 由多个数据集形成依赖时，合并到一个 `datasets` 数组。
- Job 自己读取和写入同一表不生成 Job 自依赖。
- 未解析或歧义的数据集不生成 Job 依赖。

旧版 `edges`、`self_edges` 仅在加载旧 DAG 时兼容；版本 2 生成器不再输出这两个字段。

## 执行规划安全边界

`task_run` 每次规划都先针对当前 task SQL 运行 extractor，再从同一份 fresh lineage v2
payload 生成和保存 Job DAG。普通模式允许复用 task 级抽取缓存；`--refresh-dag` 的实际
含义是向 extractor 传递 `--no-cache`。执行器不再根据旧 DAG 的 Job 名集合判断是否刷新，
也不会把旧 lineage 与新 DAG 混合使用。

执行计划同时消费两类既有证据，不重新实现生产者解析：

- 对已经解析的 process `data_dependencies`，选择 consumer 时必须同时选择 producer；
- 对 lineage 中的 `UNRESOLVED_DATASET_PRODUCER`，只要被选择的 process consumer 命中
  `not_found` 或 `multiple_candidates`，即使所有候选 Job 都在计划中也必须拒绝执行。

未选择相关 consumer 的无关子集可以继续执行；managed dataset 的依赖或诊断不会被该
process 安全边界误拦。该检查适用于默认完整 Job 集合和显式 `--job-list`，并发生在任何
数据库访问和 SQL 写入之前。

## 执行互斥

SQL 执行锁按 Doris 物理目标 `(host, port, database)` 建立，而不是按项目名或 checkout
路径建立。canonical target 的安全摘要决定锁文件名，因此同一宿主机上的主 checkout 与
worktree 会竞争同一把锁，不同 host、port 或 database 可以并行。

默认锁目录为 `tempfile.gettempdir()/dw_refactor_agent/run_locks`；
`DW_REFACTOR_AGENT_RUN_LOCK_DIR` 可以覆盖它，但覆盖值必须是绝对路径，相对路径直接
拒绝，不能按当前 checkout 的工作目录解析。所有执行器必须配置同一个绝对目录。默认目录
仅保证同一执行宿主机内互斥；多执行宿主机部署还必须把该目录放在支持 `flock` 的共享文件
系统上，或由外部调度器提供等价互斥。

## 已落地的真实资产场景

`shop` 使用 `stage_store_sales_daily` 在 `dws_store_sales_daily` 与
`dim_store_metric_snapshot` 两个 Job 之间交接。增量 base SQL 和
`full_refresh/` 下的窗口 companion SQL 都保持相同 Job I/O。过程表只由一次 CTAS
写成；原有空折扣和非法汇总行清理由 `COALESCE` 与 `HAVING` 折叠进 CTAS，避免 CTAS 后
再次更新过程表造成自写血缘和下游读取时刻不一致。CTAS 显式设置
`PROPERTIES ("replication_num" = "1")`，以兼容单 BE 的 Doris 开发/验证环境。

`retail_banking` 使用 `stage_client_transaction_daily` 在
`dws_client_transaction_daily` 与 `ads_customer_transaction_kpi_daily` 之间交接，增量与
窗口 companion 由同一生成器产生。权威来源是
`semantic_specs/dws_ads.yaml` 的 `process_table_handoff`，
`tools/generate_assets.py` 负责生成 base/full-refresh producer 和 consumer SQL；不得在
生成文件上维护第二份手工逻辑。

## 内存模型调整

### LineageTable

使用 `dataset_type` 替代 `is_transient` 和 `transient_sources`。旧版读取器可以保留 legacy
字段用于安全降级，但版本 2 序列化不再输出它们。

旧版 `is_transient=true` 无法可靠区分数据库临时表与局部普通过程表，因此读取时按
“不可跨 Job”的安全策略处理，不能自动提升为共享生产者。

### LineageJob

扩展为：

```text
name
source_file
inputs
outputs
```

版本 2 优先读取显式 `jobs`。版本 1 没有 Job 列表时，继续从 Edge 的
`source_file` 推导 Job。

### LineageEdge

新增 `job`。`source_file` 只作为版本 1 读取兼容字段存在，版本 2 输出不写该字段。

## Doris 持久化模型

### table_info

新增：

```text
dataset_type
```

旧 `is_transient` 和 `transient_sources` 在迁移期保留读取兼容，但新查询和导入以
`dataset_type` 及 Job 事实为准。

### job_dataset

新增 Job 与数据集输入输出关系表：

```text
snapshot_id
job_id
table_id
io_type       INPUT / OUTPUT
```

不增加 `dataset_scope`。局部过程表隔离由带 `job_id` 的边和生产者解析规则完成。

### column_lineage 与 table_lineage

继续通过 `job_id` 关联 Job。导入版本 2 Edge 时由 `edge.job` 查找 Job；导入版本 1 时先
将 `edge.source_file` 映射为兼容 Job。

不新增持久化 `job_dependency` 表。Job 依赖由当前快照的 `job_dataset` 和唯一生产者解析
结果派生，避免重复保存事实。

## 兼容和迁移

### Lineage JSON

- 版本 2 生成器写 `format_version`、显式 Job、带 Job 的 Edge 和结构化诊断。
- 版本 2 Edge 不写 `source_file`。
- 版本 1 读取器继续接受 `is_transient`、`transient_sources` 和 Edge `source_file`。
- 下游展示需要 SQL 文件时统一通过 Job 查找，禁止重新从表名推导任务文件。

### Job DAG

- 版本 2 生成器写 Job 节点与 `data_dependencies`。
- 加载器继续接受没有 `format_version` 的旧版 `edges/self_edges/deps/rev`。
- task runner 和 refactor 验证改用显式 Job DAG；不再要求任务文件名等于输出表名。

### 缓存

任务级缓存属于内部格式，可以继续保存 `source_file`。如果任务事实或 Edge 结构改变，
提升缓存格式或 extractor 代码版本，避免错误复用旧缓存。

## 错误处理

- Job 名重复：作为致命契约错误，不输出含歧义 Job 引用的版本 2 快照。
- Edge 引用了不存在的 Job：读取和导入时拒绝该快照。
- 数据集零生产者或多生产者：输出 warning，保留已经确认的 Job 内直接边，不生成跨 Job
  血缘或 DAG 依赖。
- Job DAG 出现环：沿用现有拓扑校验，报告环中的 Job。
- 旧版字段信息不足：采用不跨 Job的安全降级，不猜测共享生产者。

## 受影响组件

- `sql_task_facts.py`：补齐输入、普通持久化输出和准确生命周期事实。
- `lineage_extractor.py`：生成 v2 Table、Job、Edge 和 diagnostics。
- `model.py`：读取 v1/v2，增加 Job I/O 和 Edge Job 引用。
- `asset_graph.py`：按 Job 隔离局部过程表，只在唯一生产者解析后跨 Job 组合路径。
- `job_dag.py`：从显式 Job 数据依赖生成并读写 DAG v2。
- `view.py`、`query.py`、HTML 刷新逻辑：通过 Edge Job 获取任务和源文件信息。
- `import_lineage.py` 及 lineage DDL：导入 `dataset_type`、Job I/O 和 Edge Job。
- `task_run.py`：从 fresh lineage 生成显式 Job DAG，并在执行边界 fail closed。
- `run_lock.py`：按物理 Doris 目标序列化 SQL 执行，不依赖 checkout 路径。
- refactor 验证：消费显式 Job DAG，同时保留旧 DAG 读取兼容。

## 测试与验收

必须覆盖：

1. 两个 Job 各自使用同名局部过程表，只生成各自路径，不产生交叉组合。
2. 唯一普通持久化过程表生产者被另一个 Job 读取，生成跨 Job 表级、字段级和 DAG 血缘。
3. `DROP IF EXISTS; CREATE TABLE AS` 且没有后置 DROP 的表可作为共享输出候选。
4. `CREATE TEMPORARY TABLE` 不作为其他 Job 的生产者。
5. 普通表在同一 Job 创建后删除，不作为其他 Job 的生产者。
6. 没有生产者时输出 `not_found`，不生成虚假依赖。
7. 多生产者时输出 `multiple_candidates`，不根据顺序选择生产者。
8. Job 名不等于任何输出表名时仍能生成并执行正确 DAG。
9. 同一对 Job 经多个数据集依赖时合并数据集证据。
10. 孤立 Job 保留在 DAG 中。
11. Job 自读写不生成 Job 自依赖。
12. 同名但不同 catalog/database 的表不冲突。
13. 不同大小写的标识符按 canonical/casefold key 正确匹配并保留展示大小写。
14. v2 Edge 包含 `job` 且不包含 `source_file`；文件路径只能从 Job 获取。
15. v1 lineage JSON 和旧 Job DAG 仍能读取。
16. shop 与 finance_analytics 的现有血缘、执行和 refactor 流程无非预期回归。

实现完成后先运行针对性 lineage、task runner 和 refactor 测试，再按照项目约定运行完整
非 API 测试。最后执行独立 Code Review，重点检查同名隔离、生产者歧义、v1/v2 兼容、
大小写 canonical key 和执行 DAG 回归。
