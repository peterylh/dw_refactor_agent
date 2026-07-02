# lineage

## 适用范围

本文件用于血缘相关任务：`lineage/` 程序、`lineage/ddl/`、项目目录下的
`{project}/lineage/` 产物生成逻辑，以及引用血缘或 DAG 的重构验证逻辑。

如果从仓库根目录启动 Codex 并修改这些内容，也应先阅读本文件。

## 核心约定

- Doris/SQL 标识符匹配默认大小写不敏感。表名、字段名、catalog、database/schema
  在 schema lookup、字段血缘、间接依赖、CLI 查询、导入关联、DAG/资产图构建中比较时，
  应使用 canonical/casefold key。
- 区分匹配 key 与展示值：用户可见输出、lineage JSON 中已有展示字段和 SQL 表达式不应
  仅为匹配而无必要统一改成小写。
- 优先复用现有 helper，例如 `lineage.lineage_extractor` 中的
  `_canonical_identifier`、`_identifier_match_key`、`_table_identity`、
  `_schema_table_match_key` 及同类局部封装；避免在新代码里散落 ad hoc `.lower()` 或
  手写拆分规则。
- 任务级缓存、lineage JSON、HTML、DAG 输出路径应由 `config` 和现有 helper 推导，
  避免硬编码单一项目路径。

## 工具说明

### lineage_extractor.py

字段级血缘解析引擎。读取 `{project}/ods/ddl/{catalog}/{database}/`、
`{project}/mid/ddl/`、`{project}/ads/ddl/` 建表 SQL，以及
`{project}/mid/tasks/`、`{project}/ads/tasks/` ETL SQL，输出：

- `{project}/lineage/lineage_data.json`
- `{project}/lineage/task_lineage_cache.json`

全量提取默认启用 task 级血缘缓存；未变化的 task 会按 SQL、相关 DDL schema 切片、
项目 catalog/database 与 extractor 代码版本复用缓存结果。

常用参数：

- `--project shop|finance_analytics`
- `--parallel <n>`：task 文件级并行度
- `--output <path>`：指定血缘 JSON 输出文件，默认
  `{project}/lineage/lineage_data.json`
- `--cache-file <path>`：指定 task 级血缘缓存文件，默认
  `{project}/lineage/task_lineage_cache.json`
- `--no-cache`：禁用 task 级血缘缓存

```bash
# shop 项目（默认）
python lineage/lineage_extractor.py

# finance_analytics 项目
python lineage/lineage_extractor.py --project finance_analytics
```

### import_lineage.py

将 `{project}/lineage/lineage_data.json` 导入 Doris 对应 lineage 库：

- `shop` -> `shop_lineage`
- `finance_analytics` -> `finance_analytics_lineage`

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

- 项目上下文从 `config` 中的 `PROJECT_CONFIG` 推导
- HTML 模板位于 `lineage/lineage.html`、`lineage/lineage_job.html`
- HTML 输出位于项目目录，避免不同项目互相覆盖

输出位置：

- `shop` -> `shop/lineage/lineage.html`、`shop/lineage/lineage_job.html`
- `finance_analytics` -> `finance_analytics/lineage/lineage.html`、`finance_analytics/lineage/lineage_job.html`

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

## 测试提示

- 血缘相关测试在 `tests/lineage/`。
- 血缘抽取性能相关测试在 `tests/lineage/test_lineage_extraction_performance.py`。
- 项目默认全量非 API 检查是 `make test`。
- 需要快速反馈时，可以先按风险运行 `tests/lineage/` 内相关用例，再回到全量检查。
- 修改 `lineage_extractor.py` 的 SQL 解析、schema lookup、字段血缘抽取、task 缓存或
  并行抽取路径时，优先考虑运行性能相关测试；文档、DDL 或 CLI 文案小改动通常不需要。
- 血缘抽取基准在 `benchmarks/lineage_extractor/`，默认入口是 `make benchmark-lineage`。
  基准用于本地前后对比，不作为所有改动的强制验证。
- 遵守根目录 `AGENTS.md` 的测试环境要求：不要直接运行裸 `pytest`；如需指定解释器，
  使用 `make test PYTHON=/absolute/path/to/python`。
