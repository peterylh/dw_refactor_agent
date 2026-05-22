# shop-dm

## 项目概述

零售门店数据仓库建模项目。基于 Doris 构建经典分层数据仓库,并配
套字段级 SQL 血缘提取与可视化工具。

包含两个子项目:
- **shop**: 零售门店数据仓库
- **olist**: 巴西电商(Olist)数据仓库, 基于公开 Kaggle 数据集

## 技术栈

- **血缘提取**: sqlglot提供了 lineage 方法
- **环境配置**: 见 [config.py](./config.py)

## 目录结构

```
shop-dm/
├── ddl_deriver/             # DDL 变更自动推导工具
│   ├── __init__.py
│   └── ddl_deriver.py       # 核心: DDL 解析 + 变更推导引擎
├── shop/
│   ├── ddl/                 # 各层表结构定义 (纯结构，无初始化数据)
│   │   ├── ods_*.sql        # ODS 贴源层
│   │   ├── dwd_*.sql        # DWD 明细层
│   │   ├── dws_*.sql        # DWS 汇总层
│   │   └── ads_*.sql        # ADS 应用层
│   ├── data/                # 数据初始化脚本
│   │   └── ods_*.sql        # ODS 贴源层初始化数据 (INSERT INTO)
│   └── tasks/               # ETL 加工作业 SQL
│       ├── dwd_*.sql        # ods → dwd 加工
│       ├── dws_*.sql        # dwd → dws 加工
│       └── ads_*.sql        # dws → ads 加工
├── olist/                   # 巴西电商(Olist)数据仓库 (结构同 shop/)
│   ├── ddl/                 # 表结构定义 (库前缀 olist_dm.)
│   │   ├── ods_*.sql        # 9 张 ODS 表
│   │   ├── dwd_*.sql        # 4 张 DWD 纯维度表
│   │   ├── dws_*.sql        # 4 张 DWS 汇总表
│   │   └── ads_*.sql        # 7 张 ADS 应用表
│   ├── tasks/               # ETL 加工作业
│   │   ├── dwd_*.sql        # 4 个 DWD 任务
│   │   ├── dws_*.sql        # 4 个 DWS 任务
│   │   └── ads_*.sql        # 7 个 ADS 任务
│   ├── download_data.py     # 从 Kaggle 下载 Olist 数据集
│   ├── import_data.py       # Stream Load 导入 CSV → Doris
│   ├── lineage.html         # 表/列级血缘可视化
│   └── lineage_job.html     # 作业级血缘可视化
├── lineage/
│   ├── __init__.py
│   ├── ddl/                 # lineage 库表结构定义
│   │   ├── datasource.sql
│   │   ├── table_info.sql
│   │   ├── column_info.sql
│   │   ├── job.sql
│   │   ├── column_lineage.sql
│   │   ├── indirect_lineage.sql
│   │   └── table_lineage.sql
│   ├── lineage_extractor.py # SQL 字段级血缘抽取引擎
│   ├── import_lineage.py    # 血缘数据导入 lineage 库
│   ├── refresh_lineage_html.py # HTML 刷新工具
│   ├── lineage_data.json    # 血缘中间数据
│   ├── lineage.html         # 表/列级血缘可视化
│   └── lineage_job.html     # 作业级血缘可视化
├── assess/                  # 数据集市中间层评估工具
│   ├── assess_middle_layer.py # 中间层复用度/链路长度/依赖健康度/命名规范评估
│   ├── assess_result_shop.json
│   └── assess_result_olist.json
├── exec/                    # 作业执行与初始化工具
│   ├── reinit_project.py    # 数据重新初始化脚本 (清空表 -> ODS初始化 -> 重算DAG)
│   └── task_run.py          # 按 DAG 依赖顺序执行 ETL 作业
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # 共享 fixture
│   ├── ddl_deriver/         # DDL 推导相关测试
│   │   ├── __init__.py
│   │   ├── test_ddl_deriver.py
│   │   └── verify_doris_a.py
│   └── lineage/             # 血缘提取相关测试
│       ├── __init__.py
│       ├── test_build_schema.py
│       ├── test_extract_lineage.py
│       ├── test_layer_function.py
│       ├── test_trace_lineage.py
│       └── test_update_to_select.py
├── AGENTS.md
└── commit_message.md        # Git Commit 规范

- ../sqlglot/是SQLglot代码目录， 可用于研究 sqlglot实现原理和使用方式

```

## 血缘工具

### lineage_extractor.py

字段级血缘解析引擎。读取 `shop/ddl/` 的建表语句和 `shop/tasks/` 的 ETL SQL, 输出 `lineage/lineage_data.json`:

支持 `--project shop|olist` 参数:
```bash
# shop 项目 (默认)
python lineage/lineage_extractor.py
# olist 项目
python lineage/lineage_extractor.py --project olist
```

### import_lineage.py

将 `lineage_data_{project}.json` 导入到 Doris 对应项目的 lineage 库。
- shop  → `shop_lineage` 库
- olist → `olist_lineage` 库
支持 `--project shop|olist` 参数。数据按库物理隔离，Job 名无需前缀。

### refresh_lineage_html.py

读取 `lineage_data_{project}.json`, 注入到对应 HTML 中刷新血缘可视化页面。
支持 `--project shop|olist` 参数。

shop 项目: 输出到 `lineage/lineage.html` 和 `lineage/lineage_job.html`
olist 项目: 输出到 `olist/lineage.html` 和 `olist/lineage_job.html`

### lineage DDL

`lineage/ddl/` 下定义了 lineage 数据库的 7 张表: `datasource`, `table_info`, `column_info`, `job`, `column_lineage`, `indirect_lineage`, `table_lineage`。


## ETL 执行

支持 `@etl_date` 变量，用于重跑历史数据：
默认值 `CURDATE()`，不传参时按今天跑。

```bash
# 默认（当天）
mysql -h<host> -P<port> -u<user> -p<password> < shop/tasks/dwd_customer.sql

# 重跑历史某天
mysql -h<host> -P<port> -u<user> -p<password> \
  -e "SET @etl_date = '2025-01-01'; source shop/tasks/dwd_customer.sql;"

# 批量重跑（3 天维度快照 + 3 个月度）
for d in 2025-01-01 2025-01-02 2025-01-03; do
  for t in dwd_customer dwd_product dwd_store; do
    mysql -h<host> -P<port> -u<user> -p<password> \
      -e "SET @etl_date = '$d'; source shop/tasks/${t}.sql;"
  done
done
```


## 重构验证工具 (refact/)

`refact/` 下提供了一套完整的数仓重构验证工具链：

### 工作流

```bash
# 1. 分析变更 → 元数据 (检测 DDL/作业变更 + 血缘追踪 + 锚点发现 + 分区选择)
python refact/analyze_refact.py

# 2. 预览执行计划
python refact/verify_run.py --metadata refact/refact_metadata.json --dry-run

# 3. 执行验证 (自动重置验证库 + 基线建表 + DDL + SQL 表映射执行)
python refact/verify_run.py --metadata refact/refact_metadata.json

# 4. 校验对比 (支持 count / row_compare / 抽样 / 精度配置)
python refact/verify_check.py --metadata refact/refact_metadata.json --method all
```

### analyze_refact.py

重构检测脚本。通过 git diff 发现 DDL 和作业变更，利用血缘追踪下游，自动选择验证锚点和分区，输出元数据文件。

```
python refact/analyze_refact.py                          # shop 项目
python refact/analyze_refact.py --project olist           # olist 项目
python refact/analyze_refact.py --partition 2025-01-15    # 手工指定分区
python refact/analyze_refact.py --anchor ads_sales_dashboard  # 手工锚点
```

输出 `refact/refact_metadata.json`，包含：
- `baseline_ddl`: merge_base 时的完整 DDL (建表用, INSERT 数据已剥离)
- `ddl_changes`: 从 ddl_deriver 推导的 DDL 变更
- `modified_jobs` / `downstream_tables`: 变更波及范围
- `anchors`: 验证锚点 (ADS 层表)
- `partition_info`: 自动选择的最新公共分区
- `jobs_to_run`: 需执行的作业清单 (按 DWD→DWS→ADS 排序)
- `verification.checks`: 自动配置的校验项

### verify_run.py

验证执行脚本。根据元数据执行三阶段操作：

**Phase 0 - 重置**: `DROP DATABASE IF EXISTS shop_dm_qa` + `CREATE DATABASE shop_dm_qa`

**Phase 1 - 基线建表**: 用 `baseline_ddl` 还原所有表结构到 merge_base 状态。

**Phase 2 - DDL 变更**: 应用 `ddl_changes` (ALTER / CREATE / DROP / RENAME)。

**Phase 3 - 执行作业**: 按依赖顺序执行 ETL 作业。关键: **SQL Glot 表映射**：

| 表引用类型 | 改写目标 | 说明 |
|-----------|---------|------|
| DML 目标 (INSERT/UPDATE/目标等) | `shop_dm_qa.` | 写入验证库 |
| 前序已执行作业的 target | `shop_dm_qa.` | 读刚算好的 QA 数据 |
| ODS / 未修改中间表 | `shop_dm.` (保留) | 读生产数据 |

即: 作业读取生产 ODS 和已算好的中间结果，产出写入验证库，**不复制数据**。

### verify_check.py

验证校验脚本。支持可配置的校验方法：

```
python refact/verify_check.py --metadata refact/refact_metadata.json
python refact/verify_check.py --metadata refact/refact_metadata.json --method count
python refact/verify_check.py --metadata refact/refact_metadata.json --method row_compare --sample 1000
python refact/verify_check.py --metadata refact/refact_metadata.json --precision 0.001
```

| 方法 | 说明 | 参数 |
|------|------|------|
| `count` | 行数对比 | - |
| `row_compare` | 逐行逐列对比 | `--sample N` 抽样行数, `--precision 0.01` 精度容差 |

输出结果到 `refact/verify_result.json`。


## 数据集市评估工具 (assess/)

`assess/assess_middle_layer.py` 是数据集市中间层评估工具，基于血缘数据 (`lineage_data.json`) 从四个维度评估 DWD/DWS 层质量：

```
python assess/assess_middle_layer.py                           # shop 项目
python assess/assess_middle_layer.py --project olist            # olist 项目
python assess/assess_middle_layer.py --output report.json       # 指定输出路径
python assess/assess_middle_layer.py --reuse-weight 0.3 --depth-weight 0.2  # 自定义权重
python assess/assess_middle_layer.py --classify                 # 启用 LLM 智能分层巡检(DWD/DWS 表分类)
python assess/assess_middle_layer.py --classify --no-cache      # 强制重新调用 API，不使用缓存
```

| 参数 | 说明 |
|------|------|
| `--classify` | 调用 DeepSeek API 对 DWD/DWS 表进行 LLM 智能分层巡检，检测分层错配（需设置 `DEEPSEEK_API_KEY` 环境变量） |
| `--no-cache` | 配合 `--classify` 使用，跳过缓存强制重新调用 API |

### 评估维度

| 维度 | 权重(默认) | 说明 |
|------|-----------|------|
| 复用度 | 25% | 中间表被下游引用的次数，≥3 次引用满分 |
| 链路长度 | 25% | ADS 到 ODS 的 DWD/DWS 中间层深度，depth=2 最优 |
| 依赖健康度 | 25% | 检测跨层依赖违规（反向依赖、跳过中间层等） |
| 命名规范 | 25% | 表名前缀匹配分层、全小写下划线、字段命名合规 |

输出结果到 `assess/assess_result_{project}.json`。


## 分支策略

- 每次 DDL 或 ETL 变更必须在新分支上开发
- 分支命名: `feat/<描述>` 或 `refactor/<描述>`
- 完成后合并回主干并推送 GitHub


## Git Commit 规范

参见 [commit_message.md](./commit_message.md)。

## Python 编码规范

参见 [python_coding_standards.md](./python_coding_standards.md)。

## SQL 数据开发规范

参见 [sql_dev_standards.md](./sql_dev_standards.md)。
