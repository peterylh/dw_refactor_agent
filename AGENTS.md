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
config:
  materialized: snapshot
```

`task_run.py --full-refresh` 会优先读取 `ods/models/{catalog}/{database}/*.yaml`、`mid/models/*.yaml` 与 `ads/models/*.yaml` 中的 `config.materialized`，用于判断 `snapshot` / `full` / `incremental` 等执行策略。

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
- `--full-refresh`：全量刷新模式
- `--job-list`：只执行指定作业
- `--db-env`：`prod|test`
- `--refresh-dag`：先重建 `job_dag_{project}.json`
- `--parallel`：并行度

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
- `--full-refresh`：全量刷新模式
- `--parallel`：初始化与执行并行度

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

`src/dw_refactor_agent/refactor/` 提供完整的数仓重构验证工具链，当前脚本基于 `PROJECT_CONFIG` 工作，可用于 `shop`、`finance_analytics`。

本次布局迁移后，旧路径下创建的 refactor run 基线不再适用于
`warehouses/{project}/...` 新资产路径。合并该结构变更后，在途 run 应重新执行
`python -m dw_refactor_agent.refactor.run start --project <project>` 固化新基线。

### 工作流

```bash
# 1. 固化重构基线
python -m dw_refactor_agent.refactor.run start --project shop

# 2. 基于当前修改刷新血缘、评估与验证计划
python -m dw_refactor_agent.refactor.run analyze --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json

# 可选：手工指定验证分区
python -m dw_refactor_agent.refactor.run analyze --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --partition 2025-01-15

# 3. 预览旁路执行计划
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --dry-run

# 4. 执行旁路验证
python -m dw_refactor_agent.refactor.run shadow-run --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json

# 5. 对比生产与验证库结果
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --method all
```

### run.py analyze

分析入口。读取 run manifest 中的基线信息，基于当前工作区刷新血缘、变更范围、issue diff 与验证计划。

输出的 `verification/plan.json` 包含：

- `changes`：本次变更入口，例如 `modified_jobs`、`ddl_tables`、`model_tables`
  与 `config_files`
- `scope`：由变更入口推导出的验证范围，例如 `direct_tables`、`downstream_tables`、
  `assessment_tables`、`assessment_tasks` 与 `anchor_tables`
- `baseline_ddl`：merge-base 的完整 DDL（已剥离 INSERT）
- `ddl_changes`：由 `ddl_deriver` 推导的 DDL 变更
- `jobs_to_run`：按拓扑排序后的待执行作业
- `verification.compare_anchors`：compare 使用的锚点输入，包含锚点表的时间列、
  时间粒度与锚点时间值；缺少合理时间粒度时会降级为全表 compare 并输出 warning
- `verification.checks`：自动配置的校验项，包含表名、校验方法；`row_compare`
  会在配置了排除列时写入最终生效的 `exclude_columns`

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
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --method count
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --method row_compare --sample 1000
python -m dw_refactor_agent.refactor.run compare --manifest warehouses/<project>/artifacts/refactor_runs/<run_id>/manifest.json --precision 0.001
```

支持校验方法：

- `count`：行数对比
- `row_compare`：逐行逐列对比，支持 `--sample` 与 `--precision`；
  运行时字段可通过 `warehouses/{project}/warehouse.yaml` 配置排除

`row_compare` 默认从验证计划中的 `exclude_columns` 读取排除列。旧 plan
没有该字段时，compare 运行时默认忽略 `etl_time`，避免加工时间导致天然不一致。
新 plan 推荐在项目 `warehouse.yaml` 中显式配置：

```yaml
verification:
  row_compare:
    exclude_columns:
      - etl_time
    tables:
      dws_order_detail:
        exclude_columns:
          - etl_time
          - update_time
      ads_full_audit:
        exclude_columns: []
```

表级 `exclude_columns` 覆盖项目级配置；表级空列表表示该表全列比较，不忽略任何列。

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

业务语义目录默认放在项目目录下：

- `warehouses/shop/business_semantics.yaml`
- `warehouses/finance_analytics/business_semantics.yaml`

目录包含：

- `data_domains`：数据域，通常数量较少，建议人工稳定维护
- `business_areas`：业务板块
- `business_processes`：事实表/汇总事实表对应的可度量业务过程
- `semantic_subjects`：维度/实体属性表的语义主题，通常对应维表主实体

无 LLM 初始化只生成目录骨架和可用字典，不再根据表名硬猜业务过程：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --dry-run
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop
```

使用 LLM 初始化或更新目录：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --dry-run --overwrite
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --overwrite
```

等价入口：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --catalog-from-llm --dry-run --overwrite-catalog
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --catalog-from-llm --overwrite-catalog
```

LLM 目录发现会先做表级巡检，再将 fact 表指标字段中的
`business_process` 聚类为 `business_processes`，将 dimension 表主实体聚类为
`semantic_subjects`。未提供数据域/业务板块字典时，LLM 可以生成候选 code，
后续由用户在 catalog 中人工修订。表级归属会写入模型 YAML，
catalog 不长期维护 `tables`。

从已确认 catalog 初始化或刷新 models：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business
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

`dw_refactor_agent.assessment.llm.table_inspector` 是基础表巡检能力，用于单次 DeepSeek 调用中完成表级分层、表类型判断和字段分组。

`dw_refactor_agent.assessment.llm.model_metadata_writer` 用于扫描项目 DWD/DWS/DIM 层表，复用 `table_inspector` 的巡检结果，将 LLM 推断的表级元数据与事实表指标分组回写到 models。

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
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --dry-run

# 巡检 finance_analytics 并回写 models/*.yaml
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project finance_analytics

# 只回写表信息 layer/table_type
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope table

# 只回写指标分组
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope metrics

# 只回写 entities/grain
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope grain

# 从已确认 catalog 同步业务语义和基础模型元数据，不调用 LLM
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business

# 忽略缓存，强制重新调用 DeepSeek
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --no-cache

# LLM 返回校验失败时最多重试 2 次
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --max-retries 2
```

默认输出到 `warehouses/{project}/artifacts/assessment/model_metadata_result.json`。


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

参见 [docs/development/commit_message.md](docs/development/commit_message.md)。

## Python 编码规范

参见 [docs/development/python_coding_standards.md](docs/development/python_coding_standards.md)。

## SQL 数据开发规范

参见 [docs/development/sql_dev_standards.md](docs/development/sql_dev_standards.md)。
