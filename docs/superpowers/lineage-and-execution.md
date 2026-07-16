# 血缘与作业执行设计

## 场景与问题

数仓中的依赖不等于“文件名依赖”。一个 Task 可以读取多个表、写入正式表或过程表；不同 Task 也可能使用同名局部过程表。如果只按表名拼接血缘，会产生不存在的跨 Job 路径，并让执行器以错误顺序运行作业。

本设计把 SQL 中可验证的事实先建模为血缘快照，再从快照派生 Job DAG。常规执行和重构验证共享这份依赖语义。

## 核心概念

| 概念 | 含义 |
| --- | --- |
| Dataset | SQL 读取或写入的数据集，分为 `managed`、`process`、`temporary`、`external` |
| Job | 一个 Task SQL 文件对应的逻辑作业，保存输入、输出和源文件 |
| Edge | 某个 Job 内从源字段或表达式到目标字段/表的直接事实 |
| Diagnostic | 无法安全解析的事实，例如过程表没有唯一生产者 |
| Job DAG | 从 Job 输入输出关系派生的执行图，不是原始血缘事实 |
| Slice | 一个增量 Job 的执行参数、数据列和时间周期 |

`managed` Dataset 来自受管 DDL 或 Model；`process` 是普通持久化过程表；`temporary` 受数据库 Session 限制；`external` 只被当前项目读取。Dataset 类型用于描述和安全判断，不代替实际生产者证据。

## 血缘快照

血缘生成分为四步：

1. 读取所有 DDL，构建带 catalog、database、table 和 column 的当前 schema。
2. 独立解析每个 Task SQL，提取字段转换、条件依赖和表生命周期事实。
3. 汇总 Job 输入输出，解析跨 Job 的 Dataset 生产者。
4. 重新组装完整快照并校验契约，输出 `tables`、`jobs`、`edges` 和 `diagnostics`。

每条 Edge 只表达一个 Job 内能直接证明的事实。跨 Job 字段路径通过多段 Edge 在查询时组合，不把传递闭包伪装成一条直接边。

条件字段同样属于血缘。`JOIN`、`WHERE`、`GROUP BY` 等字段虽然不一定直接生成目标值，但会影响目标结果，作为间接依赖保留。

### 标识符匹配

Doris 标识符比较默认大小写不敏感。内部使用规范化的匹配 key，完整表身份至少包含 catalog、database 和 table；对外展示继续保留 SQL 中的大小写。

因此，不能在局部逻辑里用裸字符串或临时 `.lower()` 代替统一的 identifier helper。

## 过程表生产者解析

过程表既可能是 Job 内局部中间结果，也可能是跨 Job 交接数据。生产者按以下顺序解析：

```text
对 consumer Job C 读取的数据集 T：
1. 如果 C 自己生产 T，按 (C, T) 隔离，不产生 Job 自依赖；
2. 否则查找其他 Job 的持久化输出；
3. 恰好一个候选，建立 producer -> consumer 依赖；
4. 没有或存在多个候选，记录结构化诊断，不猜测生产者。
```

`CREATE TEMPORARY TABLE` 和在同一 Job 内创建后删除的表不能成为跨 Job 输出。解析不依赖文件扫描顺序、文件名排序或“最后写入者”假设。

这个算法同时保证：

- 两个 Job 使用同名局部表时不会交叉串联；
- 唯一的持久化过程表可以成为真实的跨 Job 依赖；
- 无法证明唯一性时执行器能在数据库访问前停止。

## Task 级缓存

完整血缘每次都重建，但未变化 Task 的解析结果可以复用。缓存键概念上为：

```text
hash(Task SQL
   + Task 实际引用的 schema 切片
   + 项目 catalog/database/方言配置
   + extractor 版本)
```

只要其中任一项变化，该 Task 就重新解析。最终快照从“本次缓存命中结果 + 本次新解析结果 + 当前 schema”完整组装，而不是在旧快照上打补丁，这样被删除的表、字段和 Task 不会残留。

## Job DAG

Job DAG 由血缘快照中的 Job 和已解析数据依赖生成：

- 节点是全部可执行 Job，包括没有依赖的孤立 Job；
- 边是 `producer -> consumer`，并保留形成依赖的 Dataset 作为证据；
- 正向邻接表用于下游遍历，反向邻接表用于入度和上游查询；
- 多个 Dataset 形成同一对 Job 依赖时合并证据；
- Job 自读自写不生成自依赖。

拓扑排序使用 Kahn 算法：先选择入度为零的 Job，执行完成后减少下游入度；如果最终仍有节点未输出，说明图中存在环，计划必须失败。

## 常规执行计划

常规执行在每次规划时先从当前 SQL 刷新血缘，再立即从同一份快照生成 DAG，避免“新 SQL + 旧 DAG”的混合状态。

执行器结合 DAG 与 Model YAML 中的 `execution` 生成调用：

- `incremental` Job 按 slice 参数展开一个或多个时间值；
- `full` Job 只执行一次，不继承项目默认 slice；
- full refresh 根据模型选择逐 slice 回放、companion SQL 或其他显式策略；
- 不支持历史回放的 current-state Job 遇到历史日期时明确失败或由调用方显式跳过。

Model 是执行方式的权威来源。Task 名与输出表名可以不同，执行器通过 Job 的唯一 managed 输出找到对应 Model；一个 Job 有多个 managed 输出时视为歧义。

### 子集执行安全

选择 `--job-list` 子集时，执行器检查两类条件：

1. 已解析的 process Dataset consumer 必须同时包含其 producer；
2. 被选 consumer 命中 `not_found` 或 `multiple_candidates` 诊断时禁止执行。

未选择相关 consumer 的其他子图不受影响。检查发生在任何数据库读取或写入之前。

### 并发与互斥

并发只在 DAG 已就绪的 Job 之间发生。一个 Job 只有在所有已选上游成功后才能进入 ready 队列；任一 Job 失败后不再提交新的下游任务。

`parallel` 表示全局数据库 Session 上限，不按“Job 并发 × slice 并发”重复放大。对同一物理 Doris 目标 `(host, port, database)`，整个执行过程持有同一把 advisory file lock，避免不同 checkout 或 worktree 同时写同一目标。

本机文件锁只解决共享锁目录可见范围内的并发；多执行主机需要共享 `flock` 文件系统或外部调度器提供等价互斥。

## 设计边界

- 血缘负责恢复事实，不决定业务语义是否正确。
- DAG 是血缘的执行视图，不反向成为血缘的事实来源。
- 执行器不根据表名前缀推断层级或物化方式。
- 解析不完整时允许生成带诊断的血缘快照，但涉及诊断的执行计划必须失败关闭。
- 性能基准用于发现回归，不属于运行时契约。
