# Semantic-aware compare targets：实现与持久化产物 Review

日期：2026-07-13

分支：`codex/change_target_compare`

审查范围：`2b651917..codex/change_target_compare`

## 结论

本次实现满足已确认的语义模式、最小重算、下游观察性验证、跨 run 声明复用、短 run
选择器、轻量 replan 和风险 warning 需求。第一轮代码审查发现的错误等价证明、不完整
compare 误报通过、共享 QA 溯源不可信、持久化输入未绑定等问题均已修复。

完整非 API 测试通过，shop 的等价直接表链路已真实执行 shadow-run 和 compare；unknown
链路已用真实 shop SQL 变更完成 analyze、warning、下游路由与用户声明轻量 replan 验收。
第二轮复审发现的同名外部源表 rename 误归一化和核心 API freshness 绕过也已修复。

## 需求与行为核对

| 场景 | 最终行为 |
|---|---|
| SQL 只有注释/格式变化 | AST 可证相同，自动 `equivalent` |
| 带稳定 table/column identity 的纯重命名 | 仅在目标/output 槽位可证且无命名歧义时自动 `equivalent` |
| 普通 SQL 逻辑变化 | 默认 `unknown`，不推荐任何选项 |
| 用户声明 | 直接接受 `equivalent/changed/unknown`，不要求原因 |
| 上游 `changed/unknown` | 风险向下游传播；没有有效用户声明时不能被本地自动等价覆盖 |
| equivalent 直接表 | 重算并比较本表，到此停止；未修改下游不进入 anchor |
| changed/unknown 直接表 | 沿下游重算至权威边界或观察性叶子，并输出 warning |
| 无法判断 | 比较下游，最终匹配也只能 `passed_with_warnings` |
| 用户后补声明 | `semantic-mode set --run ...` 轻量 replan；输入变化则要求 full analyze |
| partial/sample compare | 只作诊断，全部匹配仍为 `inconclusive` |

## 持久化产物详细 Review

| 产物 | 写入与 schema | 完整性/溯源 | 失效与增长 |
|---|---|---|---|
| `manifest.json` | `format_version=1`，原子 JSON 覆盖；校验必需字符串、artifacts、nested semantic intent | artifact 必须是 run 内安全相对路径；拒绝绝对路径和 `..` 逃逸 | 声明保存在对应 run，不维护单一无限增长 decisions 文件；run 目录按审计历史增长，可整目录归档/删除 |
| baseline/current lineage、`change_analysis.json` | 作为 analyze/replan 的 JSON object 输入 | plan 的 `analysis_snapshot.analysis_inputs` 分别保存三个内容 SHA-256 | 任何内容替换都会让 plan stale；轻量 replan fail closed |
| `baseline_ddl/<table>.<sha>.sql` | 同目录临时文件、flush/fsync、原子替换；文件名内容寻址 | plan ref 同时保存相对路径与原始字节 SHA-256 | 新 DDL 先写，plan 原子发布后才清理不可达旧 DDL，旧 plan 不会引用半写文件 |
| `verification/plan.json` | `format_version=1`；校验 project/db、jobs、DDL changes、verification checks、analysis snapshot 等核心类型 | `plan_fingerprint` 覆盖除自身外的规范 JSON；snapshot 绑定 workspace、lineage、change analysis、manifest 固定上下文和 semantic intent | analyze/semantic set 在生成替代 plan 前先删除旧 plan、shadow result、compare result；失败后不能继续执行旧结论 |
| `shadow_run_result.json` | QA mutation 前先原子写 `status=running`；结束后原子写最终结果 | 每次生成 UUID execution ID，并绑定 workspace/plan fingerprint | dry-run/running/failed 不能 compare；新 plan 发布时删除旧结果 |
| QA execution marker | 使用 Doris 合法表名 `dw_refactor_execution_marker`；shadow 成功后写入 | 保存 execution ID、plan fingerprint、workspace fingerprint | compare 必须从 QA 读取并精确匹配；其他 run 重建 QA 后旧结果失效 |
| 项目 execution lock | 同一项目在本机临时目录共享文件锁，不受 Git worktree 路径影响 | shadow mutation 与 compare 在同一临界区内互斥 | 防止本机并行 run 交叉改写同一 QA 数据库 |
| `compare_result.json` | `format_version=1`，原子覆盖；五态 `verification_status` | 保存 workspace/plan fingerprint、shadow execution ID、shadow result fingerprint、时间戳 | `comparison` 保存 method/sample/precision、required/executed checks 和 complete；新 plan 删除旧结果 |

## 第一轮 Review 发现与处理

| 严重度 | 发现 | 处理 |
|---|---|---|
| Critical | rename normalization 全局改写 SQL/YAML identifier，可能掩盖真实语义变化 | SQL 增加 rename usage 歧义校验；model 只归一化显式 schema reference 字段；增加 source predicate、任意语义字符串和命名碰撞回归测试 |
| Critical | `--method count` 或 `--sample` 可返回权威 passed | 引入 comparison 完整性契约；遗漏 required check 或抽样时返回 `inconclusive` |
| Critical | 本地 completed result 未证明 QA 仍属于该 execution | mutation 前写 running UUID；跨 worktree 本机锁；成功后发布 QA marker；compare 校验 exact marker |
| Important | replan 只绑定 workspace，未绑定保存的 lineage/change analysis/intent | snapshot 增加五类 analysis input fingerprint；shadow/compare/replan 全部校验 |
| Important | semantic intent 先写而 replan 失败时旧 plan 仍可执行 | 采用 fail-closed 发布：先使旧 verification outputs 失效，再写 intent/replan |
| Important | manifest/plan 只有版本号、缺少结构和路径校验 | 增加 object/type/digest/path 校验，损坏历史 manifest 诊断后跳过 |
| Important | 外置 DDL 与 plan 不是原子 bundle | DDL 内容寻址且原子写；plan 最后发布；发布成功后 GC |
| Important | compare 缺少 provenance，replan 后旧 passed 仍留存 | compare 保存完整 provenance；plan 发布主动删除 downstream results |
| Minor | row compare 只按前三列排序 | 改为按全部 projection 列排序 |
| Minor | 同秒 start 覆盖 run | exclusive mkdir，冲突使用 `_01` 等后缀 |
| Minor | 每张表重复扫描全部历史 manifest | 每次 analyze 建立一次 newest-first 声明索引 |

## 第二轮 Review 发现与处理

| 严重度 | 发现 | 处理 |
|---|---|---|
| Critical | 目标表 rename 的短名归一化仍可能把 `ext.<same_name>` 外部源表一起改写，从而误证 equivalent | identity 同时保存完整关系名；只有精确匹配的 fully-qualified 目标，或位于 INSERT/UPDATE/DELETE mutation target 的 unqualified 关系可参与 rename 证明；新增 qualified external source 回归测试 |
| Important | CLI 虽有 freshness preflight，但直接调用 `run_shadow_plan()` / `compare_shadow_results()` 可以绕过 | 新增 `require_fresh_plan_bundle()`，从标准 plan bundle 推导 manifest root/project；两个核心 API 在加载执行 plan、shadow result 或访问数据库前自行 fail closed；测试使用完整 manifest、analysis inputs 和真实 workspace fingerprint，不通过 mock 绕过 |
| Critical | 跨 worktree 直调时可能校验 manifest root A，却由进程全局 root/已加载代码 B 读取和执行资产 | workspace fingerprint 升级 v2，单独摘要实际加载的工具 package；freshness 返回绑定 manifest root 与同一内存 plan 的 `FreshPlanBundle`；planner/config/manifest/task/model 全部使用 bundle root；新增 A/B root、runtime mismatch 和 rooted config 回归测试 |
| Important | freshness 后再次读取 plan，和并发 analyze 的原子 plan 替换之间存在 TOCTOU 竞态 | 核心 API 直接物化并消费 freshness 已校验的同一 persisted plan snapshot；后续不再重新加载 plan |

## 自动化验证

执行：

```bash
make doctor
make test
```

结果：Python `3.7.12`，Ruff check/format 通过，`893 passed, 2 deselected`。

最终包含 semantic mode、plan artifact、workspace、planner、shadow-run、compare 的专项为
`180 passed`。

## shop 真实场景验收

### 1. equivalent 直接表

Run：`20260713_202349_shop`

分区：`2024-06-30`

在 `dws_store_sales_daily.sql` 只增加注释：

- `dws_store_sales_daily` 自动解析为 `equivalent/automatic`。
- `jobs_to_run` 只有 `dws_store_sales_daily`。
- authority anchor 只有 `dws_store_sales_daily`。
- 未修改的 `ads_store_performance`、`dim_store_metric_snapshot` 没有重算或 compare。
- shadow execution ID：`f39fff95-f5dd-47aa-b790-cb320c140cf4`，状态 `completed`。
- count：prod `3`，QA `3`。
- row compare：prod `3`，QA `3`，差异 `0`，仅忽略 `etl_time`。
- compare：`method=all`、`sample=0`、两个 required checks 均执行，最终 `passed`。
- workspace fingerprint v2：`sha256:55feab99dbc008bde6a833f16e761dd9d964fd0e9bcd97dc85d46c0b655d255d`。
- plan fingerprint：`sha256:1dd6f3c0135acc3136c5fb82db175fc0515ccd82f19336cc6c7668f65446af60`。

第一次真实 shadow 暴露 Doris 不允许下划线开头的 marker 表名。该问题通过失败结果中的
Doris 错误定位，先增加回归断言，再将表名改为 `dw_refactor_execution_marker`；重新
analyze 后真实 shadow 和 compare 均通过。

### 2. unknown 与上游传播

Run：`20260713_195122_shop`

分区：`2024-06-30`

在同一 DWS 聚合 SQL 增加 `store_id IS NOT NULL` 条件：

- `dws_store_sales_daily` 默认为 `unknown/default_unknown`。
- 风险传播后，`ads_store_performance`、`dim_store_metric_snapshot` 均为
  `unknown/upstream_propagation`。
- `jobs_to_run` 为 DWS 及上述两个下游作业。
- 两个下游叶子是 observational anchors；没有 authority anchor。
- analyze 对三张 unknown 表分别展示中立的 `equivalent/changed/unknown` 三选项和 warning。
- 使用 `semantic-mode set --run ... --mode unknown` 后，DWS 变为 `unknown/user`，manifest
  保存 table ID、semantic context fingerprint 和确认时间；partition 保持不变，未生成
  shadow/compare 结果。

两次验收使用的临时 SQL 改动均已恢复。

## 最终独立复审

在上述修复和最终测试后再次执行只读代码复审，覆盖 rename 证明、A/B worktree root、
runtime tool fingerprint、单一 plan snapshot、manifest/DDL 路径与摘要约束。最终未发现
Critical、Important 或 Minor finding。

## 剩余运行边界

- 文件锁解决同一主机不同进程/worktree 的并发；多主机同时操作同一 QA 数据库仍需外部
  调度保证单写。QA marker 会拒绝已被另一 execution 替换的结果，但不作为分布式锁。
- 生产数据若在 shadow 与 compare 之间变化，可能造成真实但非 SQL 重构导致的差异；当前
  结果记录精确 execution/plan，不提供生产快照隔离。
- 历史声明不集中累积，但 run 目录会按审计需求增长；清理单位应是完整 run 目录。
