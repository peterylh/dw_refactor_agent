# shop-dm

## 项目概述

基于 Doris 的分层数据仓库与重构验证项目，当前同时包含：

- **shop**: 零售门店数据仓库
- **finance_analytics**: 金融分析数仓示例

项目除常规 ODS/DWD/DWS/ADS 分层外，还包含：

- 字段级 SQL 血缘抽取与可视化
- 作业 DAG 生成与拓扑执行
- DDL 变更推导
- 数仓重构验证链路
- 中间层质量评估与 LLM 辅助分层巡检
- LLM 表级元数据、DWD/DWS 指标识别与 models 回写
- 命名规范配置化校验


## 目录结构

```text
shop-dm/
├── ddl_deriver/                    # DDL 变更自动推导工具
│   ├── __init__.py
│   └── ddl_deriver.py
├── shop/                           # 零售门店数仓
│   ├── ddl/                        # DWD/DWS/ADS/DIM 建表 SQL
│   ├── ods/                        # ODS 层资产，按 ddl/models/data/{catalog}/{database}/ 组织
│   │   ├── ddl/internal/shop_dm/    # ODS 建表 SQL
│   │   ├── models/internal/shop_dm/ # ODS 表级元数据配置
│   │   └── data/internal/shop_dm/   # ODS 初始化数据 SQL
│   ├── tasks/                      # ETL 作业 SQL
│   │   └── full_refresh/           # shop 专用批量全刷 SQL
│   └── models/                     # 表级元数据配置 (tablename.yaml)
├── finance_analytics/              # 金融分析数仓
│   ├── ddl/                        # DWD/DWS/ADS/DIM 建表 SQL
│   ├── ods/                        # ODS 层资产，按 ddl/models/data/{catalog}/{database}/ 组织
│   │   ├── ddl/internal/finance_analytics_dm/    # ODS 建表 SQL
│   │   ├── models/internal/finance_analytics_dm/ # ODS 表级元数据配置
│   │   └── data/internal/finance_analytics_dm/   # ODS 初始化数据 SQL
│   ├── tasks/                      # 可执行 ETL SQL
│   ├── models/                     # 表级元数据配置 (tablename.yaml)
│   └── generate_ods_data.py        # 生成 ODS 模拟数据 SQL
├── lineage/
│   ├── __init__.py
│   ├── ddl/                        # lineage 库快照表与核心元数据表
│   ├── lineage_extractor.py        # 字段级血缘抽取
│   ├── import_lineage.py           # 快照化批量导入 lineage 库
│   ├── lineage_cli.py              # 本地血缘查询 CLI
│   ├── refresh_lineage_html.py     # 刷新可视化 HTML
│   ├── job_dag.py                  # 基于血缘边生成作业 DAG
│   ├── task_cache.py               # 任务级血缘缓存 key 与缓存项 helpers
│   ├── lineage.html                # 字段血缘 HTML 模板
│   └── lineage_job.html            # 作业血缘 HTML 模板
├── assess/
│   ├── assess_middle_layer.py      # 中间层评估入口
│   ├── context_builder.py          # 构造 LLM 表巡检上下文
│   ├── llm/                        # DeepSeek 表巡检、字段分组与缓存
│   └── model_metadata_writer.py    # LLM 表元数据与指标分组回写
├── exec/
│   ├── reinit_project.py           # 重建 DDL + 初始化 ODS + 触发作业执行
│   └── task_run.py                 # 按 DAG 拓扑执行 ETL 作业
├── refact/
│   ├── __init__.py
│   ├── incremental_lineage.py      # 重构 run 的血缘产物构建
│   ├── run.py                      # 重构 run session 统一入口
│   ├── shadow_run.py               # 旁路执行验证计划
│   └── compare.py                  # 对比生产与验证库结果
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── assess/                     # assess/context_builder/table_inspector 测试
│   ├── ddl_deriver/                # DDL 推导与 git 模式测试
│   ├── lineage/                    # 血缘提取与 JobDAG 测试
│   ├── refact/                     # run / shadow_run / compare 测试
│   ├── test_naming_config.py       # 命名规范配置测试
│   └── test_task_run.py            # task_run 辅助逻辑测试
├── logs/                           # 本地日志与调试 SQL
├── docs/
│   └── refactor_guides/             # 数仓资产重构操作指南
├── AGENTS.md
├── commit_message.md               # Git Commit 规范
├── config.py
├── naming_config.yaml
├── python_coding_standards.md
└── sql_dev_standards.md
```

## 数仓资产重构指南

常见数仓资产重构应优先参考 `docs/refactor_guides/` 中的操作指南。

- 通用规则：参见 [docs/refactor_guides/common.md](docs/refactor_guides/common.md)
- 表重命名：参见 [docs/refactor_guides/table_rename.md](docs/refactor_guides/table_rename.md)
- 字段重命名：参见 [docs/refactor_guides/field_rename.md](docs/refactor_guides/field_rename.md)

## 血缘与 DAG 工具

### lineage_extractor.py

字段级血缘解析引擎。读取 `{project}/ddl/`、`{project}/ods/ddl/{catalog}/{database}/` 建表 SQL 与 `{project}/tasks/` ETL SQL，输出：

- `{project}/lineage/lineage_data.json`

支持 `--project shop|finance_analytics`：

```bash
# shop 项目（默认）
python lineage/lineage_extractor.py

# finance_analytics 项目
python lineage/lineage_extractor.py --project finance_analytics
```

### import_lineage.py

将 `{project}/lineage/lineage_data.json` 导入 Doris 对应 lineage 库：

- `shop` → `shop_lineage`
- `finance_analytics` → `finance_analytics_lineage`

导入采用快照化模型：

- 每次导入写入一个 `snapshot_id`
- 默认按当前时间毫秒生成快照 ID，也可用 `--snapshot-id` 指定
- 重跑同一个 `snapshot_id` 时只删除该快照的数据，不再 `TRUNCATE` 整个 lineage 库
- 导入完成后默认将当前快照标记为 active，可用 `--no-activate` 禁用
- 表、字段、作业、直接字段血缘、间接血缘、表级血缘均使用分批 `executemany`

常用参数：

- `--project shop|finance_analytics`
- `--lineage-file <path>`：指定血缘 JSON，默认 `{project}/lineage/lineage_data.json`
- `--db-env prod|test`：选择 Doris 物理环境，默认 `prod`
- `--snapshot-id <id>`：指定快照 ID，便于可重复导入或比对
- `--batch-size <n>`：控制每批 `executemany` 行数，默认 `5000`
- `--no-activate`：只导入快照，不切换 active 指针

示例：

```bash
# shop 项目，默认快照 ID，导入后设为 active
python lineage/import_lineage.py --project shop

# finance_analytics 大批量导入，放大 executemany 批次
python lineage/import_lineage.py --project finance_analytics --db-env test --batch-size 10000

# 指定快照 ID 重复导入，不切换 active
python lineage/import_lineage.py --project shop --snapshot-id 202606160001 --no-activate
```

首次部署或 DDL 变更后，需要先在对应 lineage 库中执行 `lineage/ddl/*.sql`。

### lineage_cli.py

读取本地 `{project}/lineage/lineage_data.json` 进行命令行查询，不依赖 Doris：

```bash
# 项目统计
python lineage/lineage_cli.py stats --project shop

# 表级上游/下游血缘
python lineage/lineage_cli.py table --project shop --table ads_sales_dashboard --direction upstream --depth 2

# 字段级血缘，--verbose 会展示 WHERE/GROUP BY/JOIN 等间接依赖
python lineage/lineage_cli.py column --project shop --table dws_product_sales_daily --column sales_amount --depth 2 --verbose

# 导出某张表附近的本地 HTML 子图
python lineage/lineage_cli.py export-html --project shop --table ads_sales_dashboard --depth 2 --output lineage/local_ads_sales_dashboard.html
```

`table` 支持 `--format text|json|dot`，`column` 支持 `--format text|json`。

### refresh_lineage_html.py

读取 `{project}/lineage/lineage_data.json`，将血缘数据注入 HTML 页面并刷新可视化。

支持 `--project shop|finance_analytics`。

路径规则：

- 项目上下文从 `config.py` 中的 `PROJECT_CONFIG` 推导
- HTML 模板位于 `lineage/lineage.html`、`lineage/lineage_job.html`
- HTML 输出位于项目目录，避免不同项目互相覆盖

输出位置：

- `shop` → `shop/lineage/lineage.html`、`shop/lineage/lineage_job.html`
- `finance_analytics` → `finance_analytics/lineage/lineage.html`、`finance_analytics/lineage/lineage_job.html`

示例：

```bash
# shop 项目（默认）
python lineage/refresh_lineage_html.py

# finance_analytics 项目
python lineage/refresh_lineage_html.py --project finance_analytics
```

### job_dag.py

基于血缘边构建可序列化作业 DAG，供正常执行与重构验证共用，支持：

- `bfs_downstream()` 下游追踪
- `topological_sort()` 拓扑排序
- `topological_layers()` 分层拓扑
- `save()` / `load()` DAG 持久化

生成的 DAG 文件位于：

- `{project}/lineage/job_dag.json`

### lineage DDL

`lineage/ddl/` 中维护 lineage 库的快照表与 7 张核心表：

- `lineage_snapshot`
- `datasource`
- `table_info`
- `column_info`
- `job`
- `column_lineage`
- `indirect_lineage`
- `table_lineage`

## ETL 执行与初始化

### 表级模型元数据

项目表元数据按表拆分存放在 `{project}/models/{table_name}.yaml`；ODS 表元数据可独立存放在 `{project}/ods/models/{catalog}/{database}/{table_name}.yaml`。元数据用于记录表所属层级、描述与物化方式等信息。

示例：

```yaml
version: 2
name: dwd_customer
layer: DWD
description: 客户每日快照
config:
  materialized: snapshot
```

`task_run.py --full-refresh` 会优先读取 `models/*.yaml` 与 `ods/models/{catalog}/{database}/*.yaml` 中的 `config.materialized`，用于判断 `snapshot` / `full` / `incremental` 等执行策略。

表层级以模型 YAML 中的 `layer` 为唯一权威来源；血缘与重构验证工具会读取该配置，不再通过表名前缀兜底推断层级。

### 直接执行单个 SQL

项目作业 SQL 支持 `@etl_date` 变量，默认值为 `CURDATE()`，可用于重跑历史分区：

```bash
# 默认（当天）
mysql -h<host> -P<port> -u<user> -p<password> < shop/tasks/dwd_customer.sql

# 重跑历史某天
mysql -h<host> -P<port> -u<user> -p<password> \
  -e "SET @etl_date = '2025-01-01'; source shop/tasks/dwd_customer.sql;"

# shop 维表批量重跑
for d in 2025-01-01 2025-01-02 2025-01-03; do
  for t in dwd_customer dwd_product dwd_store; do
    mysql -h<host> -P<port> -u<user> -p<password> \
      -e "SET @etl_date = '$d'; source shop/tasks/${t}.sql;"
  done
done
```

### task_run.py

按 DAG 依赖顺序执行 ETL 作业，支持：

- `--project`：`shop|finance_analytics`
- `--etl-dates`：指定 1 个或多个 ETL 日期
- `--full-refresh`：全量刷新模式
- `--job-list`：只执行指定作业
- `--db-env`：`prod|test`
- `--refresh-dag`：先重建 `job_dag_{project}.json`
- `--parallel`：并行度

示例：

```bash
# shop 全量刷新
python exec/task_run.py --project shop --full-refresh

# finance_analytics 重新生成 DAG 后执行
python exec/task_run.py --project finance_analytics --etl-dates 2025-01-15 --refresh-dag
```

### reinit_project.py

一键完成：

1. 执行 `{project}/ddl/*.sql` 与 `{project}/ods/ddl/{catalog}/{database}/*.sql` 重建表
2. 并行加载 `{project}/data/*.sql` 与 `{project}/ods/data/{catalog}/{database}/*.sql` ODS 初始化数据
3. 调用 `task_run.py` 按 DAG 执行作业

支持参数：

- `--project`：`shop|finance_analytics`
- `--db-env`：`prod|test`
- `--etl-dates`：手工指定 ETL 日期
- `--full-refresh`：全量刷新模式
- `--parallel`：初始化与执行并行度

示例：

```bash
# shop 重新初始化
python exec/reinit_project.py --project shop

# finance_analytics 测试环境重算
python exec/reinit_project.py --project finance_analytics --db-env test --etl-dates 2025-01-15

# shop 并行全刷
python exec/reinit_project.py --project shop --full-refresh --parallel 4
```

## finance_analytics 转换与造数

### generate_ods_data.py

生成 `finance_analytics/ods/data/internal/finance_analytics_dm/*.sql`
的 ODS 初始化数据，内置固定随机种子，便于复现。

直接运行：

```bash
python finance_analytics/generate_ods_data.py
```

## 重构验证工具 (refact/)

`refact/` 提供完整的数仓重构验证工具链，当前脚本基于 `PROJECT_CONFIG` 工作，可用于 `shop`、`finance_analytics`。

### 工作流

```bash
# 1. 固化重构基线
python refact/run.py start --project shop

# 2. 基于当前修改刷新血缘、评估与验证计划
python refact/run.py analyze --manifest refact/runs/<run_id>/manifest.json

# 可选：手工指定验证分区
python refact/run.py analyze --manifest refact/runs/<run_id>/manifest.json --partition 2025-01-15

# 3. 预览旁路执行计划
python refact/run.py shadow-run --manifest refact/runs/<run_id>/manifest.json --dry-run

# 4. 执行旁路验证
python refact/run.py shadow-run --manifest refact/runs/<run_id>/manifest.json

# 5. 对比生产与验证库结果
python refact/run.py compare --manifest refact/runs/<run_id>/manifest.json --method all
```

### run.py analyze

分析入口。读取 run manifest 中的基线信息，基于当前工作区刷新血缘、变更范围、issue diff 与验证计划。

输出的 `verification/plan.json` 包含：

- `baseline_ddl`：merge-base 的完整 DDL（已剥离 INSERT）
- `ddl_changes`：由 `ddl_deriver` 推导的 DDL 变更
- `modified_jobs` / `downstream_tables`：波及范围
- `anchors`：验证锚点
- `partition_info`：手工指定的验证分区信息，默认可为空
- `jobs_to_run`：按拓扑排序后的待执行作业
- `verification.checks`：自动配置的校验项

### shadow_run.py

根据验证计划执行三阶段旁路验证：

1. **Phase 0 - 重置**：重建 QA 库
2. **Phase 1 - 基线建表**：按 `baseline_ddl` 还原 merge-base 结构
3. **Phase 2 - DDL 变更**：应用 `ddl_changes`
4. **Phase 3 - 执行作业**：按依赖顺序在 QA 库运行改写后的 SQL

关键策略：作业读取生产库中的 ODS / 未变更中间表，以及已在 QA 侧重算出的中间结果；写入目标统一指向 `{project}_dm_qa`，从而做到 **不复制生产数据，仅重算必要链路**。

### compare.py

负责对比生产基线与 QA 结果，默认输出到 run 目录下的 `verification/compare_result.json`。

示例：

```bash
python refact/run.py compare --manifest refact/runs/<run_id>/manifest.json
python refact/run.py compare --manifest refact/runs/<run_id>/manifest.json --method count
python refact/run.py compare --manifest refact/runs/<run_id>/manifest.json --method row_compare --sample 1000
python refact/run.py compare --manifest refact/runs/<run_id>/manifest.json --precision 0.001
```

支持校验方法：

- `count`：行数对比
- `row_compare`：逐行逐列对比，支持 `--sample` 与 `--precision`

## 数据集市评估工具 (assess/)

元数据初始化、catalog 发现、models 刷新等完整流程参见
[docs/assess_metadata_initialization.md](docs/assess_metadata_initialization.md)。

`assess/assess_middle_layer.py` 用于评估中间层质量，当前 CLI 支持：

- `shop`
- `finance_analytics`

评估范围已扩展到 `DWD` / `DWS` / `DIM` 相关链路，支持 LLM 辅助发现：

- 分层错配
- 维度表位置不当
- 命名与依赖风险

示例：

```bash
python assess/assess_middle_layer.py
python assess/assess_middle_layer.py --project finance_analytics
python assess/assess_middle_layer.py --output report.json
python assess/assess_middle_layer.py --reuse-weight 0.3 --depth-weight 0.2
python assess/assess_middle_layer.py --llm
python assess/assess_middle_layer.py --llm --no-cache
```

参数说明：

- `--llm`：调用 DeepSeek API 进行智能分层检测
- `--no-cache`：忽略 `{project}/assess/cache/` 下的 LLM 缓存，强制重新调用

### 评估维度

| 维度 | 权重(默认) | 说明 |
|------|-----------|------|
| 复用度 | 25% | 中间表被下游引用次数，≥3 次引用满分 |
| 链路长度 | 25% | ADS 到 ODS 的 DWD/DWS/DIM 中间层深度，depth=2 最优 |
| 依赖健康度 | 25% | 检测跨层依赖、跳层依赖、反向依赖等问题 |
| 命名规范 | 25% | 表名/字段名是否符合配置化命名规范 |

结果输出到 `{project}/assess/assess_result.json`。

### 业务语义目录与 models 初始化

业务语义目录默认放在项目目录下：

- `shop/business_semantics.yaml`
- `finance_analytics/business_semantics.yaml`

目录包含：

- `data_domains`：数据域，通常数量较少，建议人工稳定维护
- `business_areas`：业务板块
- `business_processes`：事实表/汇总事实表对应的可度量业务过程
- `semantic_subjects`：维度/实体属性表的语义主题，通常对应维表主实体

无 LLM 初始化只生成目录骨架和可用字典，不再根据表名硬猜业务过程：

```bash
python assess/business_semantics_catalog.py --project shop --dry-run
python assess/business_semantics_catalog.py --project shop
```

使用 LLM 初始化或更新目录：

```bash
python assess/business_semantics_catalog.py --project shop --llm --dry-run --overwrite
python assess/business_semantics_catalog.py --project shop --llm --overwrite
```

等价入口：

```bash
python -m assess.llm.model_metadata_writer --project shop --catalog-from-llm --dry-run --overwrite-catalog
python -m assess.llm.model_metadata_writer --project shop --catalog-from-llm --overwrite-catalog
```

LLM 目录发现会先做表级巡检，再将 fact 表指标字段中的
`business_process` 聚类为 `business_processes`，将 dimension 表主实体聚类为
`semantic_subjects`。未提供数据域/业务板块字典时，LLM 可以生成候选 code，
后续由用户在 catalog 中人工修订。表级归属会写入模型 YAML，
catalog 不长期维护 `tables`。

从已确认 catalog 初始化或刷新 models：

```bash
python -m assess.llm.model_metadata_writer --project shop --from-catalog --write-scope business --dry-run
python -m assess.llm.model_metadata_writer --project shop --from-catalog --write-scope business
```

`--from-catalog --write-scope business` 不调用 LLM。表到业务过程/语义主题的归属以
项目模型 YAML 为准；catalog 只作为 code 字典和治理目录，用于校验并补齐模型中的业务域/板块信息：

- 缺失的 model 文件会被创建
- 写入或刷新 `version`、`name`、`layer`、`table_type`、`config.materialized`
- 对已有 `business_process` 的 DWD fact，从 catalog 补齐 `data_domain`
- 对已有 `business_process` 的 DWD/DWS fact，从 catalog 补齐 `business_area`
- 对已有 `semantic_subject` 的 dimension 表，保留 subject code，并移除不适用的 `business_process`

这个命令不会识别指标、不会刷新 entities/grain，不会根据 catalog 反向给表分配业务过程，也不会改 DDL、任务 SQL、表名或文件名。LLM 目录发现阶段识别出的表归属会直接写入 models，而不是长期写在 catalog 中。

### 指标识别与回写

`assess/llm/table_inspector.py` 是基础表巡检能力，用于单次 DeepSeek 调用中完成表级分层、表类型判断和字段分组。

`assess/llm/model_metadata_writer.py` 用于扫描项目 DWD/DWS/DIM 层表，复用 `assess/llm/table_inspector.py` 的巡检结果，将 LLM 推断的表级元数据与事实表指标分组回写到 models。

巡检与回写逻辑：

- 每张表只调用一次 DeepSeek，同时返回表级分层/表类型判断与字段分组
- `is_violating_declared_layer` 不由 DeepSeek 返回，由系统根据配置层和推断层计算
- LLM 推断的 `inferred_layer` / `table_type` 会回写为 models 中的 `layer` / `table_type`
- 只要 LLM 判断 `table_type=dimension`，models 中的 `layer` 强制写为 `DIM`
- 当 `table_type=dimension` 但 `inferred_layer != DIM` 时，结果 JSON 会输出元数据 warning
- `--write-scope all|table|metrics|grain|business` 控制回写范围，默认 `all`
- DWD/DWS 事实表字段按 `atomic_metrics` / `derived_metrics` / `calculated_metrics` / `dimensions` / `others` 分组
- 识别出的指标名称按 `atomic_metrics` / `derived_metrics` / `calculated_metrics` 覆盖写入对应的模型 YAML
- 派生指标通常回写到 DWS 模型；DWD 事实表中的派生/衍生指标作为 DWD 违规项写入巡检结果 JSON
- LLM 返回会按 DDL 字段名校验，结果状态分为 `passed` / `warning` / `blocked`
- 字段幻觉或重复分组会自动重试少数几次，最终仍为 `blocked` 的表不会回写 models
- `--write-scope business` 仅配合 `--from-catalog` 使用，用于从业务语义目录同步 models

示例：

```bash
# 只预览巡检与回写结果，不写模型 YAML
python -m assess.llm.model_metadata_writer --project shop --dry-run

# 巡检 finance_analytics 并回写 models/*.yaml
python -m assess.llm.model_metadata_writer --project finance_analytics

# 只回写表信息 layer/table_type
python -m assess.llm.model_metadata_writer --project shop --write-scope table

# 只回写指标分组
python -m assess.llm.model_metadata_writer --project shop --write-scope metrics

# 只回写 entities/grain
python -m assess.llm.model_metadata_writer --project shop --write-scope grain

# 从已确认 catalog 同步业务语义和基础模型元数据，不调用 LLM
python -m assess.llm.model_metadata_writer --project shop --from-catalog --write-scope business

# 忽略缓存，强制重新调用 DeepSeek
python -m assess.llm.model_metadata_writer --project shop --no-cache

# LLM 返回校验失败时最多重试 2 次
python -m assess.llm.model_metadata_writer --project shop --max-retries 2
```

默认输出到 `{project}/assess/model_metadata_result.json`。


## 本地测试环境

项目默认使用名为 `dw-refactor-py37` 的 conda 环境运行本地开发检查。主工作区与
git worktree 都应使用同一个命名环境，避免因为 worktree 路径不同而误用 Homebrew
Python 或其他全局解释器。

```bash
# 首次创建环境
make env-create

# 检查当前解释器、Python 版本与必要依赖
make doctor

# 运行非 API 测试
make test
```

不要直接运行裸 `pytest`。如需使用其他已存在解释器，必须显式指定：

```bash
make test PYTHON=/absolute/path/to/python
```


## Git Commit 规范

参见 [commit_message.md](./commit_message.md)。

## Python 编码规范

参见 [python_coding_standards.md](./python_coding_standards.md)。

## SQL 数据开发规范

参见 [sql_dev_standards.md](./sql_dev_standards.md)。
