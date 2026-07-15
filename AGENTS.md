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


## 模块地图

根 `AGENTS.md` 只保留高层模块地图，细节优先放到对应目录的专属文档或代码附近。

- `warehouses/shop/`、`warehouses/finance_analytics/`：项目数据仓库资产，包含 DDL、ODS 资产、任务 SQL 与
  表级模型 YAML。
- `src/dw_refactor_agent/lineage/`：字段级血缘抽取、查询、导入、HTML 刷新、作业 DAG 与 lineage 库 DDL。
- `src/dw_refactor_agent/assessment/`：中间层质量评估、LLM 表巡检、业务语义目录、表元数据与指标分组回写。
- `src/dw_refactor_agent/refactor/`：数仓重构验证入口、增量血缘分析、旁路执行与结果对比。
- `src/dw_refactor_agent/execution/`：项目重建、ODS 初始化与 ETL DAG 执行。
- `src/dw_refactor_agent/ddl_deriver/`：DDL 变更自动推导工具。
- `tests/`：单元测试与集成测试；血缘相关测试在 `tests/lineage/`。
- `benchmarks/`：本地性能基准；血缘抽取基准在 `benchmarks/lineage_extractor/`。
- `docs/refactor_guides/`：常见数仓资产重构操作指南。
- `warehouses/{project}/warehouse.yaml`：项目目录、库名、血缘库、命名配置和 ODS dialect 等项目配置来源。
- `src/dw_refactor_agent/config/`、`naming_config.yaml`：配置加载、路径解析、命名规范等共享代码与全局默认配置。

本地直接从源码运行 CLI 时，先执行 `pip install -e .`，或为单次命令加
`PYTHONPATH=src`。Makefile 已统一设置 `PYTHONPATH=src`。
如果使用普通安装包并在仓库根以外运行命令，需要设置
`DW_REFACTOR_AGENT_ROOT=/path/to/dw_refactor_agent`，让配置加载器找到
`warehouses/`。

## 数仓资产重构指南

常见数仓资产重构应优先参考 `docs/refactor_guides/` 中的操作指南。

- 通用规则：参见 [docs/refactor_guides/common.md](docs/refactor_guides/common.md)
- 表重命名：参见 [docs/refactor_guides/table_rename.md](docs/refactor_guides/table_rename.md)
- 字段重命名：参见 [docs/refactor_guides/field_rename.md](docs/refactor_guides/field_rename.md)

受管 DDL 必须保留稳定 schema identity。新建表后运行
`python -m dw_refactor_agent.ddl_deriver.schema_ids init-file --file <ddl_file>`；
已有表新增字段后运行 `schema_ids assign-column`；表/字段重命名必须保留原
`table_id` / `column_id`。重构完成前运行
`python -m dw_refactor_agent.ddl_deriver.schema_ids validate --project <project>`。

## 血缘与 DAG 工具

修改 `src/dw_refactor_agent/lineage/`、项目目录下的 `warehouses/{project}/artifacts/lineage/` 产物生成逻辑、血缘导入/查询或 DAG
相关逻辑时，先阅读 `src/dw_refactor_agent/lineage/AGENTS.md`。

血缘相关 SQL 标识符匹配默认大小写不敏感：表名、字段名、catalog、database/schema
在解析、查找、比较、追踪时应使用统一 canonical/casefold key；用户可见输出和 SQL
表达式可按现有逻辑保留展示大小写。

详细参数、路径规则和示例命令集中维护在 `src/dw_refactor_agent/lineage/AGENTS.md`。根目录只保留入口索引：

- `dw_refactor_agent.lineage.lineage_extractor`：字段级 SQL 血缘抽取，生成 `warehouses/{project}/artifacts/lineage/lineage_data.json` 与 task 缓存。
- `dw_refactor_agent.lineage.import_lineage`：将本地血缘 JSON 快照化导入 Doris lineage 库。
- `dw_refactor_agent.lineage.lineage_cli`：读取本地血缘 JSON 做表级/字段级查询和 HTML 子图导出。
- `dw_refactor_agent.lineage.refresh_lineage_html`：刷新项目目录下的字段血缘与作业血缘 HTML。
- `dw_refactor_agent.lineage.job_dag`：基于血缘边生成可序列化作业 DAG，供执行与重构验证复用。
- `src/dw_refactor_agent/lineage/ddl/`：维护 lineage 库快照表和核心元数据表 DDL。

## ETL 执行与初始化

### 表级模型元数据

项目表元数据按层级边界拆分存放：

- ODS：`warehouses/{project}/ods/models/{catalog}/{database}/{table_name}.yaml`
- 中间层 DIM/DWD/DWS：`warehouses/{project}/mid/models/{table_name}.yaml`
- ADS：`warehouses/{project}/ads/models/{table_name}.yaml`

元数据用于记录表所属层级、描述与物化方式等信息。

示例：

```yaml
version: 2
name: dwd_customer
layer: DWD
description: 客户每日快照
execution:
  materialized: incremental
  slice:
    param: etl_date
    column: snapshot_date
    period: D
```

`task_run.py --full-refresh` 会读取 `ods/models/{catalog}/{database}/*.yaml`、`mid/models/*.yaml` 与 `ads/models/*.yaml` 中的 `execution.materialized` 与 `execution.full_refresh_strategy`，用于判断 `incremental` / `full` 与 `replay_slices` / `companion` / `legacy_full_refresh` / `replace_all` 等执行策略。旧的 `config.materialized` 与 `config.full_refresh_strategy` 不再支持。

表层级以模型 YAML 中的 `layer` 为唯一权威来源；血缘与重构验证工具会读取该配置，不再通过表名前缀兜底推断层级。

### 直接执行单个 SQL

项目作业 SQL 支持 `@etl_date` 变量，默认值为 `CURDATE()`，可用于重跑历史分区：

```bash
# 默认（当天）
mysql -h<host> -P<port> -u<user> -p<password> < warehouses/shop/mid/tasks/dwd_customer.sql

# 重跑历史某天
mysql -h<host> -P<port> -u<user> -p<password> \
  -e "SET @etl_date = '2025-01-01'; source warehouses/shop/mid/tasks/dwd_customer.sql;"

# shop 维表批量重跑
for d in 2025-01-01 2025-01-02 2025-01-03; do
  for t in dwd_customer dwd_product dwd_store; do
    mysql -h<host> -P<port> -u<user> -p<password> \
      -e "SET @etl_date = '$d'; source warehouses/shop/mid/tasks/${t}.sql;"
  done
done
```

### task_run.py

按 DAG 依赖顺序执行 ETL 作业，支持：

- `--project`：`shop|finance_analytics`
- `--etl-dates`：指定 1 个或多个 ETL 日期
- `--etl-lookback-months`：展开截至 `--etl-end-date` 向前 N 个日历月的闭区间
- `--etl-end-date`：日期窗口结束日，默认当天
- `--full-refresh`：全量刷新模式
- `--job-list`：只执行指定作业；若包含 process dataset consumer，必须同时包含已解析的 producer
- `--db-env`：`prod|test`
- `--refresh-dag`：禁用 task cache，强制重新提取当前 SQL lineage 后生成 DAG
- `--parallel`：并行度
- `--validate-only`：仅构建并校验完整计划，不执行 SQL
- `--skip-unsupported-history`：历史补跑时跳过不支持非当天回放的 current-state 作业

实际 SQL 执行按物理目标 `(host, port, database)` 持有非阻塞 advisory file lock，
覆盖完整 producer→consumer 运行；同一宿主机上的不同 checkout/worktree 访问同一
Doris 目标时也会在首个 SQL 写入前互斥，`--validate-only` 不加锁。锁目录默认是系统
临时目录下的 `dw_refactor_agent/run_locks`，可通过
`DW_REFACTOR_AGENT_RUN_LOCK_DIR` 覆盖。覆盖值必须是绝对路径，所有执行器必须配置同一
绝对目录；默认目录只保证同一执行宿主机内互斥。多执行宿主机必须把该绝对目录放在支持
`flock` 的共享文件系统上，或由外部调度器保证等价互斥。

每次 `task_run.py` 规划都会先从当前 task SQL 刷新 lineage，再立即从同一份 v2 payload
生成并保存 Job DAG；正常模式复用 task 级缓存，`--refresh-dag` 强制 `--no-cache`。
extractor 失败会在任何数据库读取或写入前终止规划。
若任一已选 process dataset consumer 的 producer 无法唯一解析（`not_found` 或
`multiple_candidates`），无论是完整计划还是 `--job-list` 子集都会在 SQL 执行前失败；
未选择该 consumer 的无关子集不受影响。

示例：

```bash
# shop 全量刷新
python -m dw_refactor_agent.execution.task_run --project shop --full-refresh

# finance_analytics 重新生成 DAG 后执行
python -m dw_refactor_agent.execution.task_run --project finance_analytics --etl-dates 2025-01-15 --refresh-dag
```

### reinit_project.py

一键完成：

1. 执行 `warehouses/{project}/ods/ddl/{catalog}/{database}/*.sql`、`warehouses/{project}/mid/ddl/*.sql` 与 `warehouses/{project}/ads/ddl/*.sql` 重建表
2. 并行加载 `warehouses/{project}/ods/data/{catalog}/{database}/*.sql` ODS 初始化数据
3. 调用 `task_run.py` 按 DAG 执行作业

支持参数：

- `--project`：`shop|finance_analytics`
- `--db-env`：`prod|test`
- `--etl-dates`：手工指定 ETL 日期
- `--etl-lookback-months`：初始化截至结束日向前 N 个日历月的闭区间，需配合 `--full-refresh`
- `--etl-end-date`：日期窗口结束日，默认当天
- `--full-refresh`：全量刷新模式
- `--parallel`：初始化与执行并行度
- `--preserve-ods`：保留已由上游装载的 ODS，只重建并计算 MID/ADS

示例：

```bash
# shop 重新初始化
python -m dw_refactor_agent.execution.reinit_project --project shop

# finance_analytics 测试环境重算
python -m dw_refactor_agent.execution.reinit_project --project finance_analytics --db-env test --etl-dates 2025-01-15

# shop 并行全刷
python -m dw_refactor_agent.execution.reinit_project --project shop --full-refresh --parallel 4
```

## finance_analytics 转换与造数

### generate_ods_data.py

生成 `warehouses/finance_analytics/ods/data/internal/finance_analytics_dm/*.sql`
的 ODS 初始化数据，内置固定随机种子，便于复现。

直接运行：

```bash
python warehouses/finance_analytics/generate_ods_data.py
```

## 重构验证工具 (refactor)

`src/dw_refactor_agent/refactor/` 提供重构基线、增量分析、QA 旁路执行与生产/QA
结果对比工具，支持 `PROJECT_CONFIG` 中的项目。修改 refactor 代码、验证流程或
`warehouses/{project}/artifacts/refactor_runs/` 产物逻辑前，先阅读
[src/dw_refactor_agent/refactor/AGENTS.md](src/dw_refactor_agent/refactor/AGENTS.md)。

标准流程如下；参数、阶段语义、模块职责与完整输出物解释统一维护在目录级文档中。

```bash
python -m dw_refactor_agent.refactor.run start --project <project>
python -m dw_refactor_agent.refactor.run analyze --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --partition 2025-01-15
dw-refactor semantic-mode set --run <run_id> --table <table> --mode equivalent|changed|unknown
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --dry-run
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --method all
dw-refactor cleanup list --project <project>
dw-refactor cleanup delete --execution <execution_id> --yes
```

实际 shadow-run 从 `warehouse.yaml` 的 `verification.qa_database_pool` 中原子领取一个
DBA 预建的空 QA 库；不会删除或创建数据库，且执行、失败和 compare 后都保留该槽。
不同 run 可使用不同槽并发执行。只有显式 `cleanup delete` 才释放槽；不带 `--yes` 仅
预览。可按 run、execution、精确数据库名或带项目范围的时间条件筛选，legacy/invalid
槽只允许按精确数据库名清理。清理只删除槽内对象，marker 最后删除，数据库本身保留。

每个 run 位于 `warehouses/{project}/artifacts/refactor_runs/{run_id}/`：
`manifest.json` 是后续命令的稳定入口，`baseline/` 是冻结基线，`current/` 与
`analysis/` 由 analyze 刷新，`verification/` 保存 plan、shadow-run 和 compare
结果。后续命令也可使用精确 `--run <run_id>`，但不会默认选择最新 run。analyze 会按
`equivalent` / `changed` / `unknown` 解析受影响表语义；unknown 默认继续验证下游并
保留 warning。用户声明绑定 table identity 与语义上下文，可跨相同上下文的 run
复用。资产布局、schema identity 或基线解析语义变化后，旧 run 不再可靠，应重新
执行 `start` 固化基线。

## 数据集市评估工具 (assessment)

元数据初始化、catalog 发现、models 刷新等完整流程参见
[docs/assess_metadata_initialization.md](docs/assess_metadata_initialization.md)。

`dw_refactor_agent.assessment.assess_middle_layer` 用于评估中间层质量，当前 CLI 支持：

- `shop`
- `finance_analytics`

评估范围已扩展到 `DWD` / `DWS` / `DIM` 相关链路，支持 LLM 辅助发现：

- 分层错配
- 维度表位置不当
- 命名与依赖风险

示例：

```bash
python -m dw_refactor_agent.assessment.assess_middle_layer
python -m dw_refactor_agent.assessment.assess_middle_layer --project finance_analytics
python -m dw_refactor_agent.assessment.assess_middle_layer --output report.json
python -m dw_refactor_agent.assessment.assess_middle_layer --reuse-weight 0.3 --depth-weight 0.2
python -m dw_refactor_agent.assessment.assess_middle_layer --llm
python -m dw_refactor_agent.assessment.assess_middle_layer --llm --no-cache
```

参数说明：

- `--llm`：调用 DeepSeek API 进行智能分层检测
- `--no-cache`：忽略 `warehouses/{project}/artifacts/assessment/cache/` 下的 LLM 缓存，强制重新调用

### 评估维度

| 维度 | 权重(默认) | 说明 |
|------|-----------|------|
| 复用度 | 25% | 中间表被下游引用次数，≥3 次引用满分 |
| 链路长度 | 25% | ADS 到 ODS 的 DWD/DWS/DIM 中间层深度，depth=2 最优 |
| 依赖健康度 | 25% | 检测跨层依赖、跳层依赖、反向依赖等问题 |
| 命名规范 | 25% | 表名/字段名是否符合配置化命名规范 |

结果输出到 `warehouses/{project}/artifacts/assessment/assess_result.json`。

### 业务语义目录与 models 初始化

业务语义目录默认拆分放在项目目录下：

- `warehouses/{project}/business_taxonomy.yaml`
- `warehouses/{project}/business_processes.yaml`
- `warehouses/{project}/semantic_subjects.yaml`

目录包含：

- `business_taxonomy.yaml` 中的 `data_domains`：数据域，通常数量较少，建议人工稳定维护
- `business_taxonomy.yaml` 中的 `business_areas`：业务板块，建议人工稳定维护
- `business_processes.yaml` 中的 `business_processes`：事实表/汇总事实表对应的可度量业务过程
- `semantic_subjects.yaml` 中的 `semantic_subjects`：维度/实体属性表的语义主题，通常对应维表主实体

无 LLM 初始化只生成目录骨架和可用字典，不再根据表名硬猜业务过程。若项目目录仍有旧版
`business_semantics.yaml`，初始化会将其作为迁移来源，并在非 dry-run 写入完成后删除旧文件；partial-split
时只回填缺失的拆分文件，已存在 `business_taxonomy.yaml` 的 taxonomy 段和 `project_context` 不会被旧文件覆盖或合并。

命令示例：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --dry-run
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop
```

使用 LLM 初始化或更新目录：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --dry-run --overwrite
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --overwrite
```

LLM 目录发现会先做表级巡检，再将 fact 表指标字段中的
`business_process` 聚类为 `business_processes`，将 dimension 表主实体聚类为
`semantic_subjects`。数据域/业务板块只从人工 taxonomy 读取；未命中时不写入
人工主数据。表级归属会写入模型 YAML，
catalog 不长期维护 `tables`。

刷新已有 metadata：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm
```

`--mode refresh` 默认不调用 LLM。表到业务过程/语义主题的归属以
项目模型 YAML 为准；catalog 只作为 code 字典和治理目录，用于校验并补齐模型中的业务域/板块信息：

- 缺失的 model 文件会被创建
- 写入或刷新 `version`、`name`、`layer`、`table_type`、`execution.materialized`
- 对 catalog 中存在的已有 `business_process`，从 catalog 补齐适用的 `data_domain` / `business_area`
- 对 catalog 中存在的已有 `semantic_subject`，保留 subject code，并移除不适用或 stale 的 `business_process`
- 清理 stale `business_process` / `semantic_subject` 时，保留仍在 taxonomy 中的已有 `data_domain` / `business_area`
- 对还没有 `business_process` / `semantic_subject` 归属的模型，保留仍在 taxonomy 中的已有 `data_domain` / `business_area`

不加 `--llm` 时不会识别指标、不会刷新 entities/grain，不会根据 catalog 反向给表分配业务过程，也不会改 DDL、任务 SQL、表名或文件名。加 `--llm` 后会调用 table_inspector，一次巡检中更新模型的表信息、指标、entities/grain。

冷启动重建 metadata：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --llm --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --llm
```

`--mode generate` 是冷启动重建：不读取现有 models 作为推断先验，正式写入前会清空当前项目
`models/*.yaml`，再基于业务语义目录、DDL、task SQL 和 lineage 重新生成。缺少三份 split catalog YAML 时会自动补齐骨架；`--dry-run` 不删除或写入文件，只在结果 JSON 中列出 `planned_deleted_model_files` 和 `planned_catalog_written_names`，并用内存中的 catalog skeleton 继续模拟生成。只想维护 catalog 时，使用独立入口 `python -m dw_refactor_agent.assessment.business_semantics_catalog ...`。

### 指标识别与回写

`dw_refactor_agent.assessment.llm.table_inspector` 是基础表巡检能力，用于单次 DeepSeek 调用中完成表级分层、表类型判断和字段分组。

`dw_refactor_agent.assessment.llm.model_metadata_writer` 用于扫描项目 DWD/DWS/DIM 层表，复用 `table_inspector` 的巡检结果，将 LLM 推断的表级元数据与事实表指标分组回写到 models。

巡检与回写逻辑：

- 每张表只调用一次 DeepSeek，同时返回表级分层/表类型判断与字段分组
- `is_violating_declared_layer` 不由 DeepSeek 返回，由系统根据配置层和推断层计算
- LLM 推断的 `inferred_layer` / `table_type` 会回写为 models 中的 `layer` / `table_type`
- 只要 LLM 判断 `table_type=dimension`，models 中的 `layer` 强制写为 `DIM`
- 当 `table_type=dimension` 但 `inferred_layer != DIM` 时，结果 JSON 会输出元数据 warning
- DWD/DWS 事实表字段按 `atomic_metrics` / `derived_metrics` / `calculated_metrics` / `dimensions` / `others` 分组
- 识别出的指标名称按 `atomic_metrics` / `derived_metrics` / `calculated_metrics` 覆盖写入对应的模型 YAML
- 派生指标通常回写到 DWS 模型；DWD 事实表中的派生/衍生指标作为 DWD 违规项写入巡检结果 JSON
- LLM 返回会按 DDL 字段名校验，结果状态分为 `passed` / `warning` / `blocked`
- 字段幻觉或重复分组会自动重试少数几次，最终仍为 `blocked` 的表不会回写 models

示例：

```bash
# 只预览巡检与回写结果，不写模型 YAML
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm --dry-run

# 巡检 finance_analytics 并回写 models/*.yaml
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project finance_analytics --mode refresh --llm

# 从已确认 catalog 同步业务语义和基础模型元数据，不调用 LLM
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh

# 忽略缓存，强制重新调用 DeepSeek
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm --no-cache

# LLM 返回校验失败时最多重试 2 次
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm --max-retries 2
```

默认输出到 `warehouses/{project}/artifacts/assessment/model_metadata_result.json`。


## 本地测试环境

项目默认使用名为 `dw-refactor-py37` 的 conda 环境运行本地开发检查。主工作区与
git worktree 都应使用同一个命名环境，避免因为 worktree 路径不同而误用 Homebrew
Python 或其他全局解释器。
Makefile 默认通过 conda 运行时的 `CONDA_PREFIX/bin/python` 执行命令，避免
`PATH` 中的 pyenv shim、Homebrew Python 等抢先匹配 `python`。

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

如需使用其他已存在的命名 conda 环境，优先指定环境名：

```bash
make test CONDA_ENV=my-py37-env
```


## Git Commit 规范

参见 [docs/development/commit_message.md](docs/development/commit_message.md)。

## Python 编码规范

参见 [docs/development/python_coding_standards.md](docs/development/python_coding_standards.md)。

## SQL 数据开发规范

参见 [docs/development/sql_dev_standards.md](docs/development/sql_dev_standards.md)。
