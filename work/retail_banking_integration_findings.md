# `retail_banking` warehouse 接入点调研

## 结论

`retail_banking` **不需要在 Python 源码中增加手工项目注册表**。在
`warehouses/retail_banking/warehouse.yaml` 存在后，`config.core` 会自动扫描
`warehouses/*/warehouse.yaml` 并把它加入 `PROJECT_CONFIG`（
`src/dw_refactor_agent/config/core.py:155-174`）。execution、lineage、assessment、
DDL deriver 的大多数 CLI 选项都是从该配置动态生成的。

因此，安全接入的核心不是修改共享 CLI，而是满足项目资产契约：

1. 完整且可执行的 Doris DDL，一个 DDL 文件只定义一张表。
2. 每张受管表都有同名 model YAML，并用 `layer` 明确声明层级。
3. DIM/DWD/DWS/ADS 的任务文件名与目标表名一致，一个逻辑任务只产出一张持久表。
4. 每张表和每个字段都有全局唯一且稳定的 schema UUID。
5. execution slice、自动日期发现、业务语义目录和命名规范不能事后补，应当和资产一起生成。

## 1. 项目发现与配置

### 自动发现

`load_project_config()` 会按路径排序扫描 `warehouses/*/warehouse.yaml`，使用
YAML 里的 `name` 作为项目 key，否则使用目录名。新项目建议保持两者相同，
即目录与 `name` 都为 `retail_banking`。

建议配置：

```yaml
name: retail_banking
catalog: internal
database: retail_banking_dm
qa_database: retail_banking_dm_qa
lineage_database: retail_banking_lineage
naming_config: naming_config.yaml
schema_identity:
  required: true
verification:
  week_start: MON
  row_compare:
    exclude_columns:
      - etl_time
execution:
  default_slice:
    param: etl_date
    column: stat_date
    period: D
default_dialect: doris
ods_source_catalog_dialects:
  internal: doris
```

注意：Fineract 原始 Liquibase/PostgreSQL 只能作为转换输入，不能直接放到受管
ODS DDL 目录。`reinit_project` 会把发现的所有 ODS/MID/ADS DDL 直接送给
Doris 执行（`execution/reinit_project.py:137-152`）。所以最终 ODS 必须是 Doris
方言，`internal: doris` 才是正确运行时配置。

`db` / `qa_db` / `lineage_db` 都是必填的实质字段：

- execution 使用 `db`。
- refactor verification plan 直接写入 `cfg["db"]` 和 `cfg["qa_db"]`
  (`refactor/verification_plan.py:320-321`)。
- lineage import 直接连接 `cfg["lineage_db"]`。

### 不需要修改的共享注册点

下列入口都会自动读取 `PROJECT_CONFIG`：

- `execution.task_run`：`--project` choices 动态生成。
- `execution.reinit_project`：`--project` choices 动态生成。
- `lineage.lineage_extractor`、`import_lineage`、`refresh_lineage_html`。
- `assessment.assess_middle_layer`、`business_semantics_catalog`、
  `llm.model_metadata_writer`。
- `ddl_deriver.ddl_deriver git`和 `ddl_deriver.schema_ids`。
- `refactor.run start`：它还会按 `--root` 重新加载目标仓库的 warehouse
  配置，已有通用项目发现测试。

`lineage.lineage_cli` 没有 argparse choices，但是它最终通过项目路径 helper 解析
`warehouses/retail_banking/artifacts/lineage/lineage_data.json`，也不需要改代码。

## 2. 最小目录与资产布局

```text
warehouses/retail_banking/
├── warehouse.yaml
├── naming_config.yaml
├── business_taxonomy.yaml
├── business_processes.yaml
├── semantic_subjects.yaml
├── generate_ods_data.py                 # 如果采用 Python 造数
├── ods/
│   ├── ddl/internal/retail_banking_dm/*.sql
│   ├── models/internal/retail_banking_dm/*.yaml
│   └── data/internal/retail_banking_dm/*.sql
├── mid/
│   ├── ddl/*.sql
│   ├── models/*.yaml
│   └── tasks/*.sql
├── ads/
│   ├── ddl/*.sql
│   ├── models/*.yaml
│   └── tasks/*.sql
└── artifacts/                          # 生成物，不是注册条件
    ├── lineage/
    ├── assessment/
    └── refactor_runs/
```

`config.assets` 只会按上述布局发现资产：

- ODS 是 `ods/{asset_kind}/{catalog}/{database}`
  (`config/assets.py:124-194`)。
- DIM/DWD/DWS 统一放在 `mid`，ADS 放在 `ads`
  (`config/assets.py:197-230`)。
- 根目录下旧式 `ddl/` / `models/` / `tasks/` 不会被发现。

### 文件粒度

受管 schema identity 校验要求一个 DDL 文件必须且只能定义一张表
(`ddl_deriver/schema_ids.py:396-403`)。因此 Fineract 的 Liquibase changeset 不能整个
转成一个大 SQL，必须拆成约 280 个表文件。

建议对所有层保持：

```text
DDL 文件 stem == CREATE TABLE 短表名 == model.name
MID/ADS task 文件 stem == 目标表名
```

这不只是风格要求。execution planner 通过任务名反查同级 DDL，并验证 slice
字段（`execution/planner.py:280-300`）；assessment 也以 task stem 作为预期目标表。

## 3. 层级和 model YAML 契约

`layer` 是唯一权威层级来源，不再从表名前缀猜测。因此：

- 约 280 张 Fineract ODS 都要生成 model YAML，且显式 `layer: ODS`。
- 每张 DIM/DWD/DWS/ADS 也要有 model YAML。
- 非 ODS DDL 需要一个产出任务；ODS 不需要 task。
- 一个 task 应当只有一个持久目标表，一张表只有一个逻辑 writer。临时表可以在
  task 内使用，但要按现有规则命名且最终删除。

最小 ODS model 可以是：

```yaml
version: 2
name: m_client
layer: ODS
description: Fineract 客户主数据源表
execution:
  materialized: full
  full_refresh_strategy: replace_all
```

ODS 的 `execution` 实际不由 task runner 执行，但保留清晰的物化语义便于元数据治理。

MID/ADS 模型要显式声明 execution。planner 对未声明的任务默认当作
`incremental + replay_slices`，并要求 model 或 warehouse 提供 slice
(`execution/planner.py:47-79`)。建议：

- 日增量表统一含 `stat_date`，使用 warehouse 默认 D slice。
- 月表在 model 中覆盖为 `period: M`和对应时间字段。
- 静态维表明确使用 `materialized: full` + `replace_all`。
- 目前 execution/refactor 只支持 `D/M/W/H` slice，不要为季/年表配置 `Q/Y`。
  季度/年度主题可用月 slice 或 full 物化。

## 4. ODS 日期发现是最大的接入风险

`reinit_project` 和 `task_run --full-refresh` 的自动 slice 发现会：

1. 根据 model YAML 找到所有 `layer: ODS` 的已建表。
2. 对每张 ODS 执行
   `SELECT DISTINCT DATE(load_time) ...`。

该列名当前是硬编码（`execution/reinit_project.py:54-76`、
`execution/task_run.py:167-195`）。Fineract 原始表并不统一具有 `load_time`，且对
280 张表全部做 distinct 日期发现没有必要。

建议分两阶段处理：

### 最小零源码改动方案

- 为所有 Doris ODS 表增加统一技术字段 `load_time DATETIME`。
- 生成/加载 ODS 数据时始终填充它。
- 集成初期执行 `reinit_project` 时显式传 `--etl-dates`，避免全 ODS 扫描。
- `task_run --full-refresh` 同样显式传 `--etl-dates`。

### 推荐的小型共享代码改动

在 `warehouse.yaml` 增加可选配置，例如：

```yaml
execution:
  ods_date_discovery:
    tables:
      - m_savings_account_transaction
      - m_loan_transaction
      - acc_gl_journal_entry
    column: load_time
```

然后让 `reinit_project.get_etl_date_partitions()` 和
`task_run._discover_ods_dates()` 共享一个配置解析 helper。不配置时保持现有“所有
ODS + load_time”行为，可以保持 shop/finance_analytics 兼容。

这是本次接入中唯一个明显值得的共享源码改动，但不是第一批资产落盘的
阻塞项。

## 5. schema identity

`schema_identity.required: true` 应从项目创建开始就打开。批量生成 DDL 后立即
执行：

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.ddl_deriver.schema_ids init-project \
  --project retail_banking
```

然后校验：

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.ddl_deriver.schema_ids validate \
  --project retail_banking
```

校验不只检查 `retail_banking`，还会扫描所有非 fixture warehouse，以发现跨项目
`table_id` / `column_id` 冲突（`schema_ids.py:466-473`）。对几百张表批量生成
UUID 时，不要从其他 warehouse 复制已有 marker。

## 6. lineage 与 DAG

lineage extractor 按项目动态读取：

- 全部 ODS/MID/ADS DDL。
- MID/ADS task SQL。
- model YAML 中声明的层级。
- `warehouse.yaml` 的 catalog、database 和 ODS dialect。

无需为 `retail_banking` 增加特殊分支。需要遵守两个规则：

- SQL 标识符匹配大小写不敏感，不要用不同大小写制造两张逻辑表。
- 任务中涉及的永久 source/target 表都要有可解析 DDL；否则 lineage 会报
  `missing_source_ddl` / `missing_target_ddl`。

采用约 280 ODS + 120~180 中下游表后，建议用 extractor 的 task cache 和
`--parallel`，但第一次全量结果必须检查缺失 DDL 清单，不要只看进程退出码。

## 7. refactor 工作流

新项目初次接入时不存在有意义的历史 baseline。建议顺序为：

1. 先生成并验收整套 ODS/DIM/DWD/DWS/ADS 资产。
2. 生成 lineage/DAG 并通过 assessment。
3. 将资产作为一个完整基线提交。
4. 在此之后再执行 `refactor.run start --project retail_banking`。

现有 refactor 已能识别新项目下的：

- `ods|mid|ads/.../ddl/*.sql`
- `mid|ads/tasks/*.sql`
- `ods|mid|ads/.../models/*.yaml`
- `warehouse.yaml`、`naming_config.yaml`、三份 split semantics YAML

变更分类使用动态项目目录（`refactor/change_analysis.py:46-130`）。

一个需要知道的边界是：refactor DDL baseline/change derivation 只处理 `mid/ddl`和
`ads/ddl`（`refactor/verification_plan.py:85-90`）。这与 shadow-run 从生产库读取
ODS 的设计一致，但意味着 ODS DDL 改动不会像中下游 DDL 一样进入 QA DDL
change phase。对 Fineract ODS 结构改造，应单独保留 schema identity 校验与源对账测试。

## 8. assessment 与业务语义

必须同时创建：

- `business_taxonomy.yaml`：人工稳定的数据域、业务板块和 `project_context`。
- `business_processes.yaml`：事实表业务过程字典。
- `semantic_subjects.yaml`：维度/实体主题字典。
- `naming_config.yaml`：至少覆盖 DIM/DWD/DWS/ADS 和指标命名。

`finance_analytics` 的 taxonomy 已经是一个很好的起点，但不应完整复制其空的
business process/semantic subject 清单。`retail_banking` 的映射清单已经要产出业务过程和
语义主题，应直接将这些 code 回填到三份 catalog 和 model YAML，从第一版就形成闭环。

## 9. 需要增加或扩展的测试

### 必须增加

1. `tests/test_project_asset_paths.py`
   - 断言 `PROJECT_CONFIG["retail_banking"]` 的 dir/db/qa_db/lineage_db/catalog。
   - 断言 ODS 资产在 `ods/{ddl,models,data}/internal/retail_banking_dm`。
   - 断言资产数量与生成 manifest 一致。对数百表项目，更推荐根据映射 manifest
     校验表集合，不要只校验总数。
   - 校验每个 DDL 都有同名 model，每个 MID/ADS DDL 都有同名 task。
2. `tests/ddl_deriver/test_schema_ids.py`
   - 把 `retail_banking` 加到受管项目完整 ID 检查。
3. execution 测试
   - 如果不改共享日期发现逻辑，增加资产检查，保证所有 ODS DDL 都有
     `load_time`。
   - 如果实现 `execution.ods_date_discovery`，分别为 reinit/task_run 增加配置表、配置列、
     缺省兼容行为测试。
   - 为日、月、full 三类生成 model 抽样验证 planner。
4. lineage/assessment 集成检查
   - 全量 extractor 的 `missing_source_ddl` / `missing_target_ddl` 为空。
   - 任务数、DAG 节点数、层级表数与映射 manifest 一致。
   - assessment 中 asset completeness 没有缺 DDL/model/task 问题。

### 建议扩展

- `tests/test_python37_compat.py` 当前只额外扫描
  `warehouses/finance_analytics`。如果新增 `generate_ods_data.py` 或其他 Python 生成器，把
  `warehouses/retail_banking` 加入 `PROJECT_CODE_DIRS`。
- `tests/test_text_encoding_config.py` 当前只显式扫描 finance 生成器。将 retail
  生成器加入 production paths，或把该测试改为动态扫描非 fixture warehouse Python。
- 更新根 `AGENTS.md`、`src/dw_refactor_agent/lineage/AGENTS.md` 和
  `docs/refactor_guides/common.md` 中仅列出 shop/finance_analytics 的用法说明。这些是文档更新，
  不是运行时注册条件。
- 不建议立即把 `retail_banking` 加到 Makefile 默认 LLM benchmark 列表；数百表会将
  默认 benchmark 成本大幅拉高。应先作为显式可选项目运行。

## 10. 建议验证命令

遵守项目要求，不直接运行裸 `pytest`。

### 快速静态验证

```bash
make doctor

make test PYTEST_ARGS='-q -m "not api" \
  tests/test_project_asset_paths.py \
  tests/ddl_deriver/test_schema_ids.py \
  tests/test_execution_planner.py \
  tests/test_task_run.py \
  tests/test_reinit_project.py \
  tests/lineage/test_project_lineage_defaults.py \
  tests/refact/test_change_analysis.py \
  tests/refact/test_run_cli.py'
```

### schema / lineage / assessment 资产验证

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.ddl_deriver.schema_ids validate \
  --project retail_banking

PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.lineage.lineage_extractor \
  --project retail_banking --parallel 4 --no-cache

PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.lineage.lineage_cli stats \
  --project retail_banking --format json

PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.assessment.assess_middle_layer \
  --project retail_banking

PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.assessment.llm.model_metadata_writer \
  --project retail_banking --mode refresh --dry-run
```

### 数据库测试环境验证

这些命令会改变 Doris 测试库，应在静态校验全部通过后再运行。初期务必显式
给日期，避免扫描全部 ODS 表做日期发现。

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.execution.reinit_project \
  --project retail_banking --db-env test \
  --etl-dates 2025-01-15 --parallel 4

PYTHONPATH=src conda run -n dw-refactor-py37 python \
  -m dw_refactor_agent.execution.task_run \
  --project retail_banking --db-env test \
  --etl-dates 2025-01-15 --refresh-dag --parallel 4
```

### 全量回归

```bash
make test
```

## 11. 建议实施顺序

1. 先提交映射 manifest、`warehouse.yaml`、naming/taxonomy/process/subject 目录。
2. 分批生成 Doris ODS DDL + models + data，每批立即跑 schema ID 与 DDL parse 校验。
3. 生成 DIM/DWD/DWS/ADS DDL + models + tasks，先按业务域分批，再合并全量 DAG。
4. 执行 lineage + assessment，清零 missing DDL/model/task 问题。
5. 在 test Doris 库进行显式单日 reinit，再扩展到多日/全量。
6. 基线资产稳定并提交后，再启动 refactor run 工作流。

总体最小建议：**不修改项目注册和 CLI 共享源码；仅视性能需求增加可配置
ODS 日期发现 helper。** 其余变更应集中在
`warehouses/retail_banking/`、对应资产测试和文档。
